"""This file checks the json output of deepgoweb against the tsv output of deepgoplus"""

import sys
import json
import pandas as pd
import math

dgweb_file = sys.argv[1]
assert dgweb_file.endswith('.json'), f"Expected a json file, got {dgweb_file}"

dgplus_file = sys.argv[2]
assert dgplus_file.endswith('.tsv'), f"Expected a tsv file, got {dgplus_file}"


dgweb_data = json.load(open(dgweb_file))["predictions"][0]
dgweb_protein = dgweb_data["protein_info"].split("|")[1]
dgweb_predictions = dict()

for ont_data in dgweb_data["functions"]:
    for func in ont_data["functions"]:
        go_id = func[0]
        score = func[2]
        dgweb_predictions[go_id] = float(score)




with open(dgplus_file) as f:
    lines = f.readlines()
    assert len(lines) == 1, f"Expected a single line, got {len(lines)}"

    dgplus_data = lines[0].strip().split('\t')
    dgplus_protein_data = dgplus_data[0]
    dgplus_go_data = dgplus_data[1:]

    dg_plus_protein = dgplus_protein_data.split("|")[1]
    dg_plus_predictions = dict()

    for pred in dgplus_go_data:
        go_id, score = pred.split("|")
        dg_plus_predictions[go_id] = float(score)




for go_id, score in dgweb_predictions.items():
    if not go_id in dg_plus_predictions:
        raise AssertionError(f"GO ID {go_id} with score {round(score,3)} in DeepGOWeb predictions not found in DeepGOPlus predictions")

    if not (abs(score - dg_plus_predictions[go_id]) < 0.01):
        raise AssertionError(f"Scores for GO ID {go_id} do not match: DeepGOWeb: {score} != DeepGOPlus {dg_plus_predictions[go_id]}")

for go_id, score in dg_plus_predictions.items():
    if go_id in ["GO:0003674", "GO:0005575", "GO:0008150"]: # skip molecular_function, cellular_component, biological_process
        continue

    score_dgweb = math.floor(dgweb_predictions[go_id]*100)/100
    score_dgplus = math.floor(score*100)/100
    
    if not go_id in dgweb_predictions:
        raise AssertionError(f"GO ID {go_id} with score {round(score,3)} in DeepGOPlus predictions not found in DeepGOWeb predictions")

    if not (abs(score - dgweb_predictions[go_id]) < 0.01):
        raise AssertionError(f"Scores for GO ID {go_id} do not match: DeepGOPlus: {score} != DeepGOWeb {dgweb_predictions[go_id]}")

print("Predictions match")
