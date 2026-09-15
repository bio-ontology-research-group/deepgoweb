#!/usr/bin/env python

import os
import sys
import logging
import subprocess
from datetime import datetime
import requests
import json
import tempfile
import time

logging.basicConfig(filename="metadata/log.txt",
                    filemode='a',
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.DEBUG)
logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))


# MAXLEN = 2000

data_root = 'data/'
last_release_metadata = 'metadata/last_release.json'
pending_metadata = 'metadata/last_release.pending.json'


def write_json_atomic(path, payload):
    directory = os.path.dirname(path)
    fd, temporary = tempfile.mkstemp(prefix='.release-', dir=directory)
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(payload, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def recover_pending_metadata():
    if not os.path.exists(pending_metadata):
        return
    with open(pending_metadata) as handle:
        previous = json.load(handle)
    logging.warning('Recovering metadata from an interrupted update')
    write_json_atomic(last_release_metadata, previous)
    os.unlink(pending_metadata)


def require_fresh_file(path, started):
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        raise RuntimeError('Missing or empty output: ' + path)
    if os.path.getmtime(path) < started:
        raise RuntimeError('Output was not refreshed by this run: ' + path)


def download_data():
    # Downloads data from The Gene Ontology (updated monthly)
    # Downloads data from Uniprot/Swissprot (updated every few months)

    new_release = True

    try:
        if not os.path.exists(data_root):
            os.mkdir(data_root, 0o755,)


        with open(last_release_metadata, 'r') as f:
            last_release_data = json.load(f)

        last_release_version = last_release_data["current_uniprot_version"]

        logging.info('Checking new release date...')

        response = requests.get('https://rest.uniprot.org/uniprotkb/search',
                                timeout=30)

        new_release_version = response.headers['X-UniProt-Release']

        if last_release_version == new_release_version:
            logging.info('There are not new releases\nAborting...')
            new_release = False
        else:
            logging.info('SwissProt release version ' + new_release_version + ' found...')

            logging.info('Proceeding to download Gene Ontology file go.obo from http://purl.obolibrary.org/obo/go.obo')
            urlGO = 'http://purl.obolibrary.org/obo/go.obo'

            go_part = 'data/go.obo.part'
            if os.path.exists(go_part):
                os.unlink(go_part)
            subprocess.run(['wget', '--timeout=60', '--tries=5',
                            '-O', go_part, urlGO], check=True)
            if os.path.getsize(go_part) == 0:
                raise RuntimeError('Downloaded GO file is empty')
            os.replace(go_part, 'data/go.obo')

            logging.info('\nProceeding to download SwissProt file')
            urlSwiss = 'ftp://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/uniprot_sprot.dat.gz'

            swiss_part = 'data/uniprot_sprot.dat.gz.part'
            if os.path.exists(swiss_part):
                os.unlink(swiss_part)
            subprocess.run(['wget', '--timeout=60', '--tries=5',
                            '-O', swiss_part, urlSwiss], check=True)
            if os.path.getsize(swiss_part) == 0:
                raise RuntimeError('Downloaded SwissProt file is empty')
            subprocess.run(['gzip', '-t', swiss_part], check=True)
            os.replace(swiss_part, 'data/uniprot_sprot.dat.gz')

            last_release_data["current_uniprot_version"] = new_release_version


            # Update version number for the pending release.
            curr_version = last_release_data["version"].split('.')
            prefix = curr_version[:-1]
            suffix = curr_version[-1]
            last_release_data["version"] = ".".join(prefix + [str(int(suffix)+1)])


            # The old version remains recoverable until the server confirms the
            # new release. On failure or an interrupted run, restore this copy.
            with open(last_release_metadata) as f:
                previous_metadata = json.load(f)
            write_json_atomic(pending_metadata, previous_metadata)
            write_json_atomic(last_release_metadata, last_release_data)



    except Exception:
        logging.exception('Download or release detection failed')
        raise

    return new_release


def prepare_data():
    """Prepares the necessary data to train the model"""

    logging.info('In preparing data...')

    #get new swissprot.pkl through uni2pandas.py
    logging.info(f"\tRunning uni2pandas.py")
    cmd = ["python", "uni2pandas.py"]
    subprocess.run(cmd, check=True)

    #get terms.pkl, train_data.pkl and test_data.pkl through deepgoplus_data,py
    logging.info(f"\tRunning deepgoplus_data.py")
    cmd = ["python", "deepgoplus_data.py"]
    subprocess.run(cmd, check=True)
    logging.info('\nFinished preparing data...')

def train_data():
    #Trains the data by running deepgoplus.py
    started = time.time()
    cmd = ["python", "deepgoplus.py"]
    subprocess.run(cmd, check=True)
    require_fresh_file('data/model.h5', started)




###################################################################################################


def compress_data():


    with open(last_release_metadata, 'r') as f:
        last_release_data = json.load(f)
    version = last_release_data["version"]

    #date = datetime.strptime(last_release_data["current_date"], '%a, %d %b %Y %H:%M:%S GMT')
    out_file = "data/data-" + version + '.tar.gz'

    go_file="data/go.obo"
    diamond_db="data/train_data.dmnd"
    model="data/model.h5"
    result_diamond="data/test_diamond.res"
    predictions="data/predictions.pkl"
    train_pkl="data/train_data.pkl"
    train_fa="data/train_data.fa"
    test_pkl="data/test_data.pkl"
    test_fa="data/test_data.fa"

    terms="data/terms.pkl"

    release="data/RELEASE.md"
    release_html="data/RELEASE.html"

    metadata = "metadata/last_release.json"


    package_files = [go_file, diamond_db, model, result_diamond, predictions,
                     train_pkl, train_fa, test_pkl, test_fa, terms,
                     release, release_html, metadata]
    for path in package_files:
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            raise RuntimeError('Cannot package missing or empty file: ' + path)

    temporary_archive = out_file + '.part'
    if os.path.exists(temporary_archive):
        os.unlink(temporary_archive)
    subprocess.run(['tar', '-czf', temporary_archive] + package_files, check=True)
    subprocess.run(['gzip', '-t', temporary_archive], check=True)
    os.replace(temporary_archive, out_file)

    return out_file[5:]


def metrics_from_files():

    started = time.time()
    cmd = ["bash", "new_evaluation.sh"]
    subprocess.run(cmd, check=True)

    for path in ('data/train_data.dmnd', 'data/test_diamond.res',
                 'results/deepgoplus_mf.txt', 'results/deepgoplus_bp.txt',
                 'results/deepgoplus_cc.txt'):
        require_fresh_file(path, started)

    mf = open('results/deepgoplus_mf.txt').readlines()
    bp = open('results/deepgoplus_bp.txt').readlines()
    cc = open('results/deepgoplus_cc.txt').readlines()

    mf_smin = mf[2].split(':')[1]
    mf_fmax = mf[3].split(':')[1]
    mf_aupr = mf[4].split(':')[1]

    bp_smin = bp[2].split(':')[1]
    bp_fmax = bp[3].split(':')[1]
    bp_aupr = bp[4].split(':')[1]

    cc_smin = cc[2].split(':')[1]
    cc_fmax = cc[3].split(':')[1]
    cc_aupr = cc[4].split(':')[1]

    return mf_smin, mf_fmax, mf_aupr, bp_smin, bp_fmax, bp_aupr, cc_smin, cc_fmax, cc_aupr


def release_notes_file():
    # Will generate data/RELEASE.md and data/RELEASE.html files.

    with open(last_release_metadata, 'r') as f:
            last_release_data = json.load(f)

    version = last_release_data["version"]

    file_html = open('data/RELEASE.html', 'w')
    file_md = open('data/RELEASE.md', 'w')
    go_file = open('data/go.obo', 'r')
    mf_smin, mf_fmax, mf_aupr, bp_smin, bp_fmax, bp_aupr, cc_smin, cc_fmax, cc_aupr = metrics_from_files()

    go_file.readline()
    go_date =  str(datetime.strptime(go_file.readline().rstrip('\n').split('/')[1], '%Y-%m-%d').date())
    swissprot_version = last_release_data["current_uniprot_version"]


    text_md = """
# DeepGOPlus: Improved protein function prediction from sequence
DeepGOPlus is a novel method for predicting protein functions from
protein sequences using deep neural networks combined with sequence
similarity based predictions.
# Release information
Current version is """ + version + """. The model in the current release was trained using the Gene Ontology
released on """ + go_date + """ and the SwissProt data with version """ + swissprot_version +  """.
The obtained results are the following:
For MFO:
    Fmax:   """ + mf_fmax +"""
    Smin:   """ + mf_smin +"""
    AUPR:   """ + mf_aupr +"""
For BPO:
    Fmax:   """ + bp_fmax + """
    Smin:   """ + bp_smin + """
    AUPR:   """ + bp_aupr + """
For CCO:
    Fmax:   """ + cc_fmax + """
    Smin:   """ + cc_smin + """
    AUPR:   """ + cc_aupr + """
For more information about the project, please look at https://github.com/bio-ontology-research-group/deepgoplus
"""

    text_html = """

<p>
The current version release is """ + version + """. The model in the current release was trained using the Gene Ontology
# released on """ + go_date + """ and the SwissProt data with version """ + swissprot_version +""".
</p>

<p>
The obtained results are the following:
</p>

<table class="table table-striped">
<thead>
<tr><th></th>
<th>Fmax</th>
<th>Smin</th>
<th>AUPR</th>
</tr></thead>
<tbody>
<tr><td>MFO</td><td>""" + mf_fmax + """</td><td>""" + mf_smin+ """</td><td>""" + mf_aupr+"""</td></tr>
<tr><td>BPO</td><td>""" + bp_fmax + """</td><td>""" + bp_smin+ """</td><td>""" + bp_aupr+"""</td></tr>
<tr><td>CCO</td><td>""" + cc_fmax + """</td><td>""" + cc_smin+ """</td><td>""" + cc_aupr +"""</td></tr>
</tbody>
</table>

"""

    file_md.write(text_md)
    file_html.write(text_html)
    file_md.close()
    file_html.close()
    go_file.close()


def upload_data(filename):
    cmd = ["ssh", "-o", "BatchMode=yes", os.environ["PUBLISH_HOST"],
           os.environ["PUBLISH_COMMAND"], filename]
    subprocess.run(cmd, check=True)

def main():
    for name in ("PUBLISH_HOST", "PUBLISH_COMMAND"):
        if not os.environ.get(name):
            raise RuntimeError('Missing private publication setting: ' + name)
    recover_pending_metadata()
    try:
        logging.info("Downloading data...")
        downloaded = download_data()
        if not downloaded:
            return
        logging.info("Preparing data...")
        prepare_data()
        logging.info("Training...")
        train_data()
        logging.info("Generating release notes...")
        release_notes_file()
        logging.info("Compressing output data...")
        out_file_name = compress_data()
        logging.info("Compressed file name: %s", out_file_name)
        logging.info("Uploading to server...")
        upload_data(out_file_name)
        os.unlink(pending_metadata)
        logging.info("Release committed successfully")
    except Exception:
        logging.exception('Update failed; release not committed')
        recover_pending_metadata()
        raise

if __name__ == "__main__":
    main()
