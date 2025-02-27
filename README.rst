====
bws
====


BWS is a Django app to run web-services for `BOADICEA <https://canrisk.org/about/>`_.

Quick start
-----------

1. Installation::

    pip install -e git+https://git@github.com/CCGE-BOADICEA/bws.git#egg=bws

2. Update the ``bws.settings.py``. In particular change the ``FORTRAN_HOME`` parameter to set the directory location for the cancer risk models. Depending on the file structure it may be necessary to also change the ``HOME`` location in ``BC_MODEL`` and ``OC_MODEL`` in this file. These and the ``PROBS_EXE`` and ``RISKS_EXE`` parameters define the location of the executables for the mutation probability and risk calculation::

    FORTRAN_HOME = "/usr/src/"
    ....
    
    #
    # BREAST CANCER MODEL
    BC_MODEL = {
        'NAME': 'BC',
        'HOME': os.path.join(FORTRAN_HOME, 'boadicea'),
        'PROBS_EXE': 'boadicea_probs.exe',
        'RISKS_EXE': 'boadicea_risks.exe',
    ....

3. If you do not have access to the vcf2prs module, then comment out the related imports in the ``bws.settings.py``::

    #import vcf2prs
    #from vcf2prs import SnpFile, Vcf2PrsError

and change the get_alpha function to return as follows::

    def get_alpha(ref_file):
    ''' Get PRS alpha from a reference file header. '''
     return
    #    moduledir = os.path.dirname(os.path.abspath(vcf2prs.__file__))
    #    ref_file = os.path.join(moduledir, "PRS_files", ref_file)
    #    try:
    #        snp_file = open(ref_file, 'r')
    #        alpha = SnpFile.extractAlpha(snp_file.__next__())
    #    except (IOError, UnicodeDecodeError, StopIteration):
    #        raise Vcf2PrsError('Error: Unable to open the file "{0}".'.format(ref_file))
    #    finally:
    #        snp_file.close()
    #    return alpha

4. If you need to start a Django project::

    django-admin startproject [project_name]

5. Add "rest_framework", "rest_framework.authtoken" and "bws" to your ``INSTALLED_APPS`` in ``settings.py``::

    INSTALLED_APPS = (
        ...
        'rest_framework',
        'rest_framework.authtoken',
        'bws',
    )

6. Import the bws settings in ``settings.py``::

    from bws.settings import *
  
7. Add web-service endpoints to the ```urls.py``::

     from bws import rest_api
     from rest_framework.authtoken.views import ObtainAuthToken
     from django.conf.urls import include, url
     ....
     
	 url_rest_patterns = [
	     url(r'^boadicea/', rest_api.BwsView.as_view(), name='bws'),    # breast cancer risk model
	     url(r'^ovarian/', rest_api.OwsView.as_view(), name='ows'),     # ovarian cancer risk model
	     url(r'^auth-token/', ObtainAuthToken.as_view()),
	 ]
	 urlpatterns.extend(url_rest_patterns)

8. Run tests::

    python manage.py test bws.tests.test_bws \
                          bws.tests.test_ows.OwsTests \
                          bws.tests.test_throttling \
                          bws.tests.tests_pedigree_validation

Note: To set-up the BWS web-services to use the polygenic risk score (PRS) and cancer risk factor
components (i.e. used with BOADICEA v5 or higher) requires extra Django Permissions to be granted.

The `run_webservice.py <https://github.com/CCGE-BOADICEA/bws/blob/master/bws/scripts/run_webservice.py>`_ 
script can be used to submit requests to the BWS web-service. It takes a username and
pedigree file and will prompt for the password and run the risk calculation via the web-service::

    ${PATH_TO_BWS}/bws/scripts/run_webservice.py --help
    ${PATH_TO_BWS}/bws/scripts/run_webservice.py --url ${URL} -u ${USER} \
                                                 -p ${PATH_TO_BWS}/bws/tests/data/pedigree_data.txt 

To run the conversion script
----------------------------

1. Open a terminal and go  to the desired path (e.g. with `cd`).::

    cd ./to/desired/directory/

2. Clone (or download the project)::

    git clone https://github.com/ulaval-rs/bws
    cd bws

3. Make a new Python environment (this assume that you have access to `python` from the terminal).::

    python -m venv venv

4. Install the project dependencies::

    ./venv/bin/pip install -r requirements.txt

5. Copy-paste the `dev.env` to `.env`. This will contain the environment variables needed to run the scripts.::

    cp dev.env .env

6. Fill the `.env` file with the correct information (`REDCAP_TOKEN`, `REDCAP_URL` and `REDCAP_PEDIGREE_VARIABLE`).

7. Run the `retrieve.py` file. This file retrieve the pedigree files
(at specified `REDCAP_PEDIGREE_VARIABLE`) from REDCap and store them at `./data/pedigree/`.::

    ./venv/bin/python ./bws/scripts/retrieve.py

8. If no error occurs, there should be .txt files at `./data/pedigree/`.
9. Now to convert the .txt files to .csv files, run the following script::

    ./venv/bin/python ./bws/scripts/canrisk_2_csv.py

10. CSV files should be at `./data/new_pedigree/`, and the merged CSV file at `./data/merged_pedigree.csv`