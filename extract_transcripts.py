import re

def create_filename(text):
    # Remove line numbers, convert to lowercase, replace non-alphanumeric with underscore
    words = re.sub(r'^\d+→', '', text).lower().split()
    # Take first 3-5 meaningful words
    meaningful_words = [word for word in words if len(word) > 2][:5]
    filename = '_'.join(meaningful_words)
    return filename if filename else 'unnamed_transcript'

def extract_transcripts(input_file, output_dir):
    with open(input_file, 'r') as f:
        content = f.read()

    # Split by the () pattern with newline before and after
    transcripts = re.split(r'\n\(\) \n', content)

    transcript_count = 0
    for transcript in transcripts:
        if not transcript.strip():
            continue

        transcript_count += 1

        # Try to create a meaningful filename, fallback to numbered filename
        try:
            filename = create_filename(transcript.split('\n')[0])
        except:
            filename = f'chunk6_{transcript_count:03d}'

        filepath = f'{output_dir}/{filename}.txt'

        with open(filepath, 'w') as f:
            f.write(transcript.strip())

    return transcript_count

# Specify input and output paths
input_file = '/Users/hvamsi/code/creditcard/all_transcripts_combined.txt'
output_dir = '/Users/hvamsi/code/creditcard/organized_transcripts'

# Extract transcripts and print count
total_transcripts = extract_transcripts(input_file, output_dir)
print(f"Total transcripts extracted: {total_transcripts}")