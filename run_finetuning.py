
import os
from openai import OpenAI

client = OpenAI()

try:
    # 1. Upload the file
    print("Uploading file...")
    training_file = client.files.create(
        file=open("C:\\Users\\Admin\\project3\\finetuning_snapshot.jsonl", "rb"),
        purpose="fine-tune"
    )
    print(f"File uploaded successfully with ID: {training_file.id}")

    # 2. Create a fine-tuning job
    print("Creating fine-tuning job...")
    job = client.fine_tuning.jobs.create(
        training_file=training_file.id,
        model="gpt-3.5-turbo"
    )
    print(f"Fine-tuning job created successfully with ID: {job.id}")
    print("You can monitor the job status on the OpenAI website.")
    print(f"Job details: {job}")

except Exception as e:
    print(f"An error occurred: {e}")
    # Try to get more specific error details from the API response if available
    if hasattr(e, 'response') and e.response:
        print(f"API Response: {e.response.text}")
