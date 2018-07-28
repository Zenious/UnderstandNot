import boto3
from extractAudio import AudioExtract
from readJSON import Transcribe
<<<<<<< HEAD
=======
from ffprobe3 import FFProbe
>>>>>>> 766f1857d59687035d74131d5b8e8aef834abe55

dynamodb = boto3.resource('dynamodb')

def aws_stuff(index):
    table = dynamodb.Table('Videos')
<<<<<<< HEAD
    table.update_item(
        Key= {'id': index},
        UpdateExpression = "SET job_status = :job_status",
        ExpressionAttributeValues={':job_status': 'Extratcing Audio'}
        )
    # TODO upload video to S3 Bucket
    audio_file = AudioExtract.extractFLAC(index)
    # TODO upload audio to S3 Bucket
=======
    metadata = FFProbe('./resources/{}'.format(index))
    is_video = False
    for stream in metadata.streams:
        if stream.is_video():
            is_video = True
            video_length = int(stream.duration_seconds())
            table.update_item(
                Key= {'id': index},
                UpdateExpression = "SET video_length = :video_length",
                ExpressionAttributeValues={':video_length': video_length}
                )
            break

    if not is_video:
        table.update_item(
            Key= {'id': index},
            UpdateExpression = "SET job_status = :job_status",
            ExpressionAttributeValues={':job_status': 'Invalid Video File'}
            )
        #TODO delete file
        return
    table.update_item(
        Key= {'id': index},
        UpdateExpression = "SET job_status = :job_status",
        ExpressionAttributeValues={':job_status': 'Extracting Audio'}
        )
    audio_file = AudioExtract.extractFLAC(index)
>>>>>>> 766f1857d59687035d74131d5b8e8aef834abe55
    bucket = 'orbitalphase1'
    s3 = boto3.client('s3')
    s3.upload_file(audio_file, bucket, audio_file)

<<<<<<< HEAD
    # TODO send req to transcribe
=======
>>>>>>> 766f1857d59687035d74131d5b8e8aef834abe55
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