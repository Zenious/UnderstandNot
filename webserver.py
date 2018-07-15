from sanic import Sanic
from sanic import response
import uuid 
import boto3
import urllib
from redis import Redis
from rq import Queue, get_current_job
from rq_worker import aws_stuff
from sanic_jinja2 import SanicJinja2
from readJSON import Transcribe
from hashlib import md5
import json
from boto3.dynamodb.conditions import Attr
import time

app = Sanic()
app.config.REQUEST_MAX_SIZE = 1000000000 # 1GB
app.static('/r', './resources')
app.static('/static', './static')

jinja = SanicJinja2(app)
redis_connection = Redis()
q = Queue(connection=redis_connection)
dynamodb = boto3.resource('dynamodb')


@app.route('/')
@jinja.template('index.html')
async def index(request):
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
        index =  uuid.uuid4().hex
        create_file(index, file_body)
        hashcode = compute_md5(file_body)

        #TODO check duplicates

        table = dynamodb.Table('Videos')
        table.put_item(Item={
            'id': index,
            'title': file_name,
            'hash': hashcode,
            'job_status': 'Queue for Audio Extraction',
            'transcript': None,
            'subs': None,
            'vote_count': 0,
            'upload_date': int(time.time()) # time in seconds
            } )

        q.enqueue(aws_stuff, index, timeout='2h', job_id=index)
        return response.redirect('/job/{}'.format(index))

    else:
        create_file(file_name, file_body)
        trans = Transcribe()
        trans.parseOutput(file_name)
        return response.text(file_type)

def create_file(filename, data):
    f = open('./resources/{}'.format(filename), 'wb')
    f.write(data)
    f.close()

def compute_md5(data):
    m = md5()
    m.update(data)
    return m.digest()

@app.route('/parse', methods=['POST'])
async def post_transcribe(request):
    Transcribe.parseOutput()
    return response.text("TODO")

@app.route('/search')
async def search_redirect(request):
    inputs = request.args
    return response.redirect('/search/{}'.format(inputs['search'][0]))


@app.route('/search/<title>')
@jinja.template('search.html')
async def search(request, title):
    # get GET Parameters
    table = dynamodb.Table('Videos')
    db_query = table.scan(
        FilterExpression=Attr('title').contains(title),
        ConsistentRead=True
        )
    items = db_query['Items']
    extract_title = lambda x:x['title']
    extract_id = lambda x:x['id']
    results = []
    for item in items:
        info = {}
        info.update({'title': extract_title(item)})
        info.update({'id' : extract_id(item)})
        results.append(info)
    return {'results': results}


@app.route('/job/<id>')
@jinja.template('job.html')
async def retrieve_job(request, id):
    jinja_response = {}

    table = dynamodb.Table('Videos')
    db_query = table.get_item(
        Key={'id':id},
        ConsistentRead=True
        )
    db_item = db_query['Item']
    job_status = db_item['job_status']
    title = {'title': db_item['title']}
    timestamp = {'date': time.asctime(time.gmtime(db_item['upload_date']))}
    count = db_item.get('vote_count')
    if count is None:
        count = 0
    jinja_response.update({'status': job_status})
    jinja_response.update(title)
    jinja_response.update(timestamp)
    if job_status == 'Sent Audio For Transcription':
        duration = {'duration': db_item['video_length']}
        jinja_response.update(duration)
        transcribe = boto3.client('transcribe')
        result = transcribe.get_transcription_job(
            TranscriptionJobName=id)

        status = result['TranscriptionJob']['TranscriptionJobStatus']
        jinja_response.update({'status': status})
        if status == 'COMPLETED':
            status = 'Transcription done'
            trans_uri = result['TranscriptionJob']['Transcript']['TranscriptFileUri']
            trans_file = './resources/trans{}'.format(id)
            path_file = 'trans{}'.format(id)
            urllib.request.urlretrieve(trans_uri,trans_file)
            trans = Transcribe()
            trans.parseOutput(trans_file)
            table = dynamodb.Table('Videos')
            trans_data = {}
            with open(trans_file, "r") as f:
                trans_data = json.load(f)
            table.update_item(
                Key= {'id': id},
                UpdateExpression = "SET job_status=:job_status, transcript=:transcript",
                ExpressionAttributeValues={
                    ':job_status': 'Transcription done',
                    ':transcript': trans_data
                    }
                )
            jinja_response.update({'status': status})
            jinja_response.update({'srt': path_file, 'flac': id, 'ready': True, 'count': count})
            return jinja_response
        else: 
            return jinja_response
    elif job_status == 'Transcription done':
        jinja_response.update({
            'flac': id,
            'srt': 'trans{}'.format(id),
            'ready': True,
            'count': count
            })
        return jinja_response
    else:
        return jinja_response
       

@app.route('/video/<id>')
@jinja.template('video.html')
async def video(request, id):
    t = Transcribe()
    srt_filename = './resources/trans{}.srt'.format(id)
    path_file = 'trans{}.srt'.format(id)
    t.srt_to_vtt(srt_filename)
    return {
    'vtt': path_file,
    'id': id
    }

@app.route('/vote')
async def vote(request):
    args = request.args
    query_id = args.get('id')
    query_vote = args.get('vote')
    print(args)
    table = dynamodb.Table('Videos')
    db_query = table.get_item(
        Key={'id':query_id},
        ConsistentRead=True
    )
    item = db_query['Item']
    count_vote = item.get('vote_count')
    if count_vote is None:
        count_vote = 0
    if query_vote == 'yes':
        count_vote += 1
    else:
        count_vote -= 1
    print (count_vote)

    table.update_item(
        Key= {'id': query_id},
        UpdateExpression = "SET vote_count=:count_vote",
        ExpressionAttributeValues={
            ':count_vote': count_vote
            }
    )
    return response.json({'status': 'ok', 'count': count_vote})

@app.route('/milestone2')
async def milestone(request):
    return response.redirect('https://drive.google.com/open?id=1bVEeyqf3NGO7y332PS1Mbob6_EXEUA4o')

@app.route('/job_queue')
async def get_queue_length(request):
    queue_length = len(q)
    job = get_current_job(connection=redis_connection)
    return response.json({'status':'ok', 'queue_length':queue_length, 'current_job': job})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, workers=10)