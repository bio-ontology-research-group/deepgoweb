FROM tensorflow/tensorflow:1.15.5-py3

RUN pip install --no-cache-dir \
    "numpy==1.18.5" \
    "protobuf==3.19.6" \
    "pandas" \
    "tqdm" \
    "absl-py" \
    "biopython" \
    "tensorflow_hub==0.7.0" \
    "scipy" \
    "scikit-learn"

WORKDIR /pf
