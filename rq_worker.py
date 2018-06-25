import boto3
from extractAudio import AudioExtract
from readJSON import Transcribe

dynamodb = boto3.resource('dynamodb')

def aws_stuff(index):
    table = dynamodb.Table('Videos')
    table.update_item(
        Key= {'id': index},
        UpdateExpression = "SET job_status = :job_status",
        ExpressionAttributeValues={':job_status': 'Extratcing Audio'}
        )
    # TODO upload video to S3 Bucket
    audio_file = AudioExtract.extractFLAC(index)
    # TODO upload audio to S3 Bucket
    bucket = 'orbitalphase1'
    s3 = boto3.client('s3')
    s3.upload_file(audio_file, bucket, audio_file)

    # TODO send req to transcribe
    transcribe = boto3.client('transcribe')

    result = transcribe.start_transcription_job(
        TranscriptionJobName=index,
        LanguageCode='en-US',
        MediaSampleRateHertz=44100,
        MediaFormat='flac',
        Media={
            'MediaFileUri': 'https://s3-us-east-2.amazonaws.com/{}/{}'.format(bucket,audio_file)
        }
    )
    table.update_item(
        Key= {'id': index},
        UpdateExpression = "SET job_status = :job_status",
        ExpressionAttributeValues={':job_status': 'Sent Audio For Transcription'}
    )