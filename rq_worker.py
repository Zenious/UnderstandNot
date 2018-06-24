import boto3
from extractAudio import AudioExtract
from readJSON import Transcribe

def aws_stuff(index):
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