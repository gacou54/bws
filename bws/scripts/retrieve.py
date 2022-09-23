import os
import time

import redcap
import requests
from dotenv import load_dotenv

load_dotenv('.env')

REDCAP_TOKEN = os.environ.get('REDCAP_TOKEN')
REDCAP_URL = os.environ.get('REDCAP_URL')
REDCAP_PEDIGREE_VARIABLE = os.environ.get('REDCAP_PEDIGREE_VARIABLE')


def pedigree_generator(project):
    participants = project.export_records(format_type='df', fields=['record_id'])

    for record_id in participants.index:
        if record_id in ['1', '2']:
            continue

        if os.path.exists(f'./data/pedigree/{record_id}.txt'):
            continue

        file_content = None
        time.sleep(0.2)
        try:
            file_content, _ = project.export_file(record=record_id, field=REDCAP_PEDIGREE_VARIABLE)
            file_content = file_content.decode()

        except requests.RequestException:
            print(f'Record ID {record_id}: no pedigree file')

        yield record_id, file_content


if __name__ == '__main__':
    project = redcap.Project(REDCAP_URL, token=REDCAP_TOKEN)

    if not os.path.exists('./data'):
        os.makedirs('./data/pedigree')

    for record_id, pedigree in pedigree_generator(project):
        if pedigree is not None:
            with open(f'./data/pedigree/{record_id}.txt', 'w') as file:
                file.write(pedigree)




