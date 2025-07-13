import pandas as pd
import numpy as np
import re
import pickle
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.utils import to_categorical
import os
import langdetect

models_path = "Models/"
all_files = os.listdir(models_path)
file_names = [f for f in all_files if f.endswith('.h5')]
files_names = file_names.sort(key=lambda x: int(x.split('_v')[1].split('.')[0]))
latest_model = file_names[-1] if file_names else None
print(f"Latest model: {latest_model}")

# Ensure the script runs in the correct directory
csv_path = '/Dataset/song_lyrics_subset.csv'  # Path to full CSV
batch_size = 100                # Number of lyrics per chunk
batch_index = 1                  # Set to 0 for first 1000, 1 for next 1000, etc.


def is_english(text):
    try:
        return langdetect.detect(text) == 'en'
    except:
        return False


model_path = latest_model  # Path to your saved model
tokenizer_path = 'tokenizer.pkl'     # Path to your saved tokenizer

def clean_text(text):
    text = str(text).lower()
    text = text.replace('\n', ' ')
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'[,\.!?()]', '', text)
    text = re.sub(r'\w*\d\w*',' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'[^a-z0-9\s\n\']', '', text)
    return text

skip = 1 + (batch_index * batch_size)  # skip header + previous rows
df = pd.read_csv(csv_path, usecols=['lyrics'], skiprows=range(1, skip), nrows=batch_size)
df = df[df['lyrics'].apply(is_english)]
df['lyrics'] = df['lyrics'].apply(clean_text)
df = df[df['lyrics'].str.strip().astype(bool)]

with open(tokenizer_path, 'rb') as f:
    tokenizer = pickle.load(f)

# ------------------------
# CONVERT TO SEQUENCES
# ------------------------
sequences = tokenizer.texts_to_sequences(df['lyrics'])
sequences = [s for s in sequences if len(s) > 5]

input_sequences = []
for seq in sequences:
    for i in range(1, len(seq)):
        n_gram_seq = seq[:i+1]
        input_sequences.append(n_gram_seq)

if not input_sequences:
    raise ValueError("No valid sequences generated from this chunk.")

max_seq_len = max(len(x) for x in input_sequences)
input_sequences = pad_sequences(input_sequences, maxlen=max_seq_len, padding='pre')

X = input_sequences[:, :-1]
y = to_categorical(input_sequences[:, -1], num_classes=len(tokenizer.word_index) + 1)

model = load_model(model_path)

model.compile(
    loss='categorical_crossentropy',
    optimizer='adam',
    metrics=['accuracy']
)

# OPTIONAL: Resize input shape if needed (in case new batch has longer sequences)
model.build(input_shape=(None, X.shape[1]))

model.fit(X, y, epochs=5, batch_size=128)

new_model_path = f"song_generator_v{batch_index+1}.h5"
model.save(new_model_path)
print(f"Model saved as {new_model_path}")
