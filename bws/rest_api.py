''' API for the BWS REST resources. '''
from collections import OrderedDict
import datetime
import logging
import os
import subprocess

from django.conf import settings
from rest_framework import serializers, status
from rest_framework.authentication import BasicAuthentication, \
    TokenAuthentication  # SessionAuthentication
from rest_framework.exceptions import NotAcceptable
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView
from rest_framework_xml.renderers import XMLRenderer

from boadicea import pedigree
from boadicea.pedigree import PedigreeFile
import tempfile
import shutil


logger = logging.getLogger(__name__)


class BurstRateThrottle(UserRateThrottle):
    """ Throttle short burst of requests from a user. """
    scope = 'burst'
    rate = '60/min'


class SustainedRateThrottle(UserRateThrottle):
    """ Throttle sustained requests from a user. """
    scope = 'sustained'
    rate = '1000/day'


class BwsInputSerializer(serializers.Serializer):
    ''' Boadicea result. '''
    pedigree_data = serializers.CharField()
    mut_freq = serializers.ChoiceField(choices=['UK', 'Ashkenazi', 'Iceland', 'Custom'],
                                       default='UK', help_text="Mutation frequency")
    for gene in settings.GENES:
        exec(gene.lower() + "_mut_frequency = serializers.FloatField(required=False)")

    for gene in settings.GENES:
        exec(gene.lower() + "_mut_sensitivity = serializers.FloatField(required=False, default=" +
             str(settings.GENETIC_TEST_SENSITIVITY[gene]) + ", max_value=1, min_value=0)")
    cancer_rates = serializers.ChoiceField(choices=list(settings.CANCER_RATES.keys()))

#     def validate(self, attrs):
#         """ Validate input parameters. """
#         mut_freq = attrs.get('mut_freq')
#         if mut_freq == 'Custom':
#             for gene in settings.GENES:
#                 mf = attrs.get(gene.lower() + '_mut_frequency')
#                 if not self.isfloat(mf):
#                     raise serializers.ValidationError(
#                         gene+" has an invalid (non-float) mutation frequency value = "+str(mf))
#         return attrs

#     def isfloat(self, value):
#         """
#         Return true if the given value a float.
#         """
#         try:
#             float(value)
#             return True
#         except:
#             return False


class PedigreeResultSerializer(serializers.Serializer):
    family_id = serializers.CharField()
    cancer_risks = serializers.ListField(required=False)
    mutation_probabilties = serializers.ListField()


class BwsOutputSerializer(serializers.Serializer):
    """ Boadicea result. """
    version = serializers.CharField()
    timestamp = serializers.DateTimeField()
    mutation_frequency = serializers.DictField()
    mutation_sensitivity = serializers.DictField()
    cancer_incidence_rates = serializers.CharField()
    pedigree_result = PedigreeResultSerializer(many=True)
    warnings = serializers.ListField(required=False)


class BwsView(APIView):
    renderer_classes = (XMLRenderer, JSONRenderer, BrowsableAPIRenderer, )
    serializer_class = BwsInputSerializer
    authentication_classes = (BasicAuthentication, TokenAuthentication, )
    permission_classes = (IsAuthenticated,)
    throttle_classes = (BurstRateThrottle, SustainedRateThrottle)

    def get_serializer_class(self):
        return BwsInputSerializer

    def post(self, request):
        """
        BOADICEA Web-Service (BWS)
        ---
        parameters_strategy: merge
        response_serializer: BwsOutputSerializer
        parameters:
           - name: pedigree_data
             description: BOADICEA pedigree data file
             type: file
             required: true
           - name: mut_freq
             description: mutation frequency
             required: true
             type: string
             paramType: form
             defaultValue: 'UK'
             enum: ['UK', 'Ashkenazi', 'Iceland', 'Custom']
           - name: brca1_mut_frequency
             description: BRCA1 mutation frequency (only available with mut_freq=Custom)
             required: false
             type: float
             paramType: form
           - name: brca2_mut_frequency
             description: BRCA2 mutation frequency (only available with mut_freq=Custom)
             required: false
             type: float
             paramType: form
           - name: palb2_mut_frequency
             description: PALB2 mutation frequency (only available with mut_freq=Custom)
             required: false
             type: float
             paramType: form
           - name: atm_mut_frequency
             description: ATM mutation frequency (only available with mut_freq=Custom)
             required: false
             type: float
             paramType: form
           - name: chek2_mut_frequency
             description: CHEK2 mutation frequency (only available with mut_freq=Custom)
             required: false
             type: float
             paramType: form
           - name: cancer_rates
             description: cancer incidence rates
             required: true
             type: string
             paramType: form
             defaultValue: 'UK'
             enum: ['UK', 'UK-version-1', 'Australia', 'USA-white', 'Denmark', 'Finland',
             'Iceland', 'New-Zealand', 'Norway', 'Sweden']

           - name: brca1_mut_sensitivity
             description: BRCA1 mutation sensitivity
             required: false
             type: float
             paramType: form
             defaultValue: 0.7
           - name: brca2_mut_sensitivity
             description: BRCA2 mutation sensitivity
             required: false
             type: float
             paramType: form
             defaultValue: 0.8
           - name: palb2_mut_sensitivity
             description: PALB2 mutation sensitivity
             required: false
             type: float
             paramType: form
             defaultValue: 0.9
           - name: atm_mut_sensitivity
             description: ATM mutation sensitivity
             required: false
             type: float
             paramType: form
             defaultValue: 0.9
           - name: chek2_mut_sensitivity
             description: CHEK2 mutation sensitivity
             required: false
             type: float
             paramType: form
             defaultValue: 1.0

        responseMessages:
           - code: 401
             message: Not authenticated

        consumes:
           - application/json
           - application/xml
        produces: ['application/json', 'application/xml']
        """
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid(raise_exception=True):
            file_obj = request.FILES.get('pedigree_data')
            if file_obj is not None:
                pedigree_data = ''
                for chunk in file_obj.chunks():
                    pedigree_data += chunk.decode("utf-8")
            else:
                pedigree_data = request.data.get('pedigree_data')

            pf = PedigreeFile(pedigree_data)
            population = request.data.get('mut_freq', 'UK')
            cancer_rates = settings.CANCER_RATES.get(request.data.get('cancer_rates'))

            if population != 'Custom':
                mutation_frequency = settings.MUTATION_FREQUENCIES[population]
            else:
                mutation_frequency = {}
                for gene in settings.GENES:
                    mutation_frequency[gene] = float(request.POST.get(gene.lower() + '_mut_frequency'))

            mutation_sensitivity = {
                k: float(request.data.get(k.lower() + "_mut_sensitivity", settings.GENETIC_TEST_SENSITIVITY[k]))
                for k in settings.GENETIC_TEST_SENSITIVITY.keys()
            }

            output = {
                "version": settings.BOADICEA_VERSION,
                "timestamp": datetime.datetime.now(),
                "mutation_frequency": {population: mutation_frequency},
                "mutation_sensitivity": mutation_sensitivity,
                "cancer_incidence_rates": cancer_rates,
                "pedigree_result": []
            }

            warnings = pf.validate()
            if len(warnings) > 0:
                output['warnings'] = warnings

            cwd = tempfile.mkdtemp(prefix=str(request.user)+"_", dir="/tmp")
            for pedi in pf.pedigrees:
                this_pedigree = {}
                this_pedigree["family_id"] = pedi.famid

                # mutation probability calculation
                if pedi.is_carrier_probs_viable():
                    ped_file = pedi.write_pedigree_file(file_type=pedigree.MUTATION_PROBS,
                                                        filepath=os.path.join(cwd, "test_prob.ped"))
                    bat_file = pedi.write_batch_file(pedigree.MUTATION_PROBS, ped_file,
                                                     filepath=os.path.join(cwd, "test_prob.bat"),
                                                     mutation_freq=mutation_frequency,
                                                     sensitivity=mutation_sensitivity)
                    probs = self._run(request, pedigree.MUTATION_PROBS, bat_file, cancer_rates=cancer_rates,
                                      cwd=cwd, size=len(pedi.people))
                    this_pedigree["mutation_probabilties"] = self.parse_probs_output(probs)

                # cancer risk calculation
                if pedi.is_risks_calc_viable():
                    ped_file = pedi.write_pedigree_file(file_type=pedigree.CANCER_RISKS,
                                                        filepath=os.path.join(cwd, "test_risk.ped"))
                    bat_file = pedi.write_batch_file(pedigree.CANCER_RISKS, ped_file,
                                                     filepath=os.path.join(cwd, "test_risk.bat"),
                                                     mutation_freq=mutation_frequency,
                                                     sensitivity=mutation_sensitivity)
                    risks = self._run(request, pedigree.CANCER_RISKS, bat_file, cancer_rates=cancer_rates,
                                      cwd=cwd, size=len(pedi.people))
                    this_pedigree["cancer_risks"] = self.parse_risks_output(risks)
                output["pedigree_result"].append(this_pedigree)

            shutil.rmtree(cwd)
            output_serialiser = BwsOutputSerializer(output)
            return Response(output_serialiser.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def _run(self, request, process_type, bat_file, cancer_rates="UK", cwd="/tmp",
             size=settings.MAX_PEDIGREE_SIZE):
        """
        Run a process.
        """
        from subprocess import Popen, PIPE
        prog = ""
        out = ""
        if process_type == pedigree.MUTATION_PROBS:
            prog = os.path.join(settings.FORTRAN_HOME, "./boadicea_probs_v10.exe")
            out = "can_probs"
        else:
            prog = os.path.join(settings.FORTRAN_HOME, "./boadicea_risks_v10.exe")
            out = "can_risks"

        niceness = int(size/15)
        if niceness > 19:
            niceness = 19
        process = Popen([prog,
                         bat_file,  # "Sample_Pedigrees/risks_single_person.bat",
                         os.path.join(settings.FORTRAN_HOME, "Data/locus.loc"),
                         out+".stdout",
                         out+".out",
                         os.path.join(settings.FORTRAN_HOME, "Data/incidence_rates_" + cancer_rates + ".nml")],
                        cwd=cwd,
                        stdout=PIPE,
                        preexec_fn=lambda: os.nice(niceness))

        (_output, _err) = process.communicate()
        try:
            exit_code = process.wait(timeout=60*4)  # timeout in seconds

            if exit_code == 0:
                with open(os.path.join(cwd, out+".out"), 'r') as result_file:
                    data = result_file.read()
                logger.info("BWS " +
                            ("mutation " if process_type == pedigree.MUTATION_PROBS else "risk ") +
                            "calculation, user = "+str(request.user))
                return data
            else:
                logger.error("EXIT CODE ("+out.replace('can_', '')+"): "+str(exit_code))
                logger.error(_output)
                raise NotAcceptable("Error: " + str(exit_code))
        except subprocess.TimeoutExpired:
            process.terminate()
            logger.error("BOADICEA process timed out as the pedigree is too large or complex to process.")
            raise NotAcceptable("Error: BOADICEA process timed out as the pedigree is too large or complex to process.")

    def parse_risks_output(self, risks):
        """
        Parse computed cancer risk results.
        """
        lines = risks.split(sep="\n")
        risks_arr = []
        for line in lines:
            if pedigree.BLANK_LINE.match(line):
                continue
            parts = line.split(sep=",")
            risks_arr.append(OrderedDict([
                ("age", int(parts[0])),
                ("breast cancer risk", {
                    "decimal": float(parts[1]),
                    "percent": float(parts[2])
                }),
                ("ovarian cancer risk", {
                    "decimal": float(parts[3]),
                    "percent": float(parts[4])
                })
            ]))
        return risks_arr

    def parse_probs_output(self, probs):
        """
        Parse computed mutation carrier probability results.
        """
        parts = probs.strip().split(sep=",")
        probs_arr = [{"no mutation": {"decimal": float(parts[0]), "percent": float(parts[1])}}]
        for i, gene in enumerate(settings.GENES):
            probs_arr.append({gene:
                              {"decimal": float(parts[((i*2)+2)]),
                               "percent": float(parts[(i*2)+3])}})
        return probs_arr
