from sanic import Sanic
from sanic import response
import uuid 
import boto3
import urllib
from redis import Redis
from rq import Queue
from rq_worker import aws_stuff
from sanic_jinja2 import SanicJinja2
from readJSON import Transcribe


app = Sanic()
app.config.REQUEST_MAX_SIZE = 1000000000 # 1GB
app.static('/static', '.')

jinja = SanicJinja2(app)
redis_connection = Redis()
q = Queue(connection=redis_connection)
# dynamodb = boto3.resource('dynamodb', region_name='us-west-2', endpoint_url="http://localhost:8001")


@app.route('/')
@jinja.template('index.html')
async def test(request):
    return 


@app.route('/upload', methods=['POST'])
async def post_upload(request):
    if 'file' not in request.files:
        return response.text('no files')
    file = request.files['file']
    file_body = file[0].body
    file_name = file[0].name
    file_type = file[0].type

    # check if is valid filetype
    if 'video' in file_type:
        # generate db record for index
        index =  uuid.uuid4().hex
        # table = dynamodb.Table('Videos')
        # table.put_item(Item={
        #     'id': index,
        #     'title': file_name
        #     } )

        create_file(index, file_body)
        q.enqueue(aws_stuff, index)
        return response.redirect('/job/{}'.format(index))

    else:
        create_file(file_name, file_body)
        trans = Transcribe()
        trans.parseOutput(file_name)
        return response.text(file_type)

def create_file(filename, data):
    f = open(filename, 'wb')
    f.write(data)
    f.close()

@app.route('/parse', methods=['POST'])
async def post_transcribe(request):
    Transcribe.parseOutput()
    return response.text("TODO")

@app.route('/job/<id>')
@jinja.template('job.html')
async def retrieve_job(request, id):
    transcribe = boto3.client('transcribe')
    result = transcribe.get_transcription_job(
        TranscriptionJobName=id)

    status = result['TranscriptionJob']['TranscriptionJobStatus']

    if status == 'COMPLETED':
        trans_uri = result['TranscriptionJob']['Transcript']['TranscriptFileUri']
        trans_file = 'trans{}'.format(id)
        urllib.request.urlretrieve(trans_uri,trans_file)
        trans = Transcribe()
        trans.parseOutput(trans_file)

        return {
        'status': status,
        'srt': trans_file,
        'flac': id
        }

@app.route('/video/<id>')
@jinja.template('video.html')
async def video(request, id):
    return {
    'id': id
    }

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8010, workers=10)