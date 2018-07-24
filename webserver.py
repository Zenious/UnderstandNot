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
from sanic.exceptions import NotFound, ServerError, abort
from sanic.log import logger as log
import base64
from sanic_session import Session, InMemorySessionInterface

app = Sanic()
app.config.REQUEST_MAX_SIZE = 1000000000 # 1GB
app.static('/r', './resources')
app.static('/static', './static')
session = Session(app, interface=InMemorySessionInterface())

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
        return response.redirect('/')
    file = request.files['file']
    file_body = file[0].body
    file_name = file[0].name
    file_type = file[0].type
    if "" in [file_body, file_name,file_type]:
        return response.redirect('/')
    # check if is valid filetype
    if 'video' in file_type:
        index =  uuid.uuid4().hex
        create_file(index, file_body)
        hashcode = compute_md5(file_body)
        log.info('hash generated = {}'.format(hashcode))
        table = dynamodb.Table('Videos')

        db_query = table.scan(
            FilterExpression=Attr('hash').contains(hashcode),
            Limit=1,
            ConsistentRead=True
            )
        items = db_query['Items']
        if len(items) > 0:
            b64hash = base64.b64encode(hashcode)
            return response.redirect('/hash/{}'.format(b64hash.decode("ascii")))

        table.put_item(Item={
            'id': index,
            'title': file_name,
            'hash': hashcode,
            'job_status': 'Queue for Audio Extraction',
            'transcript': None,
            'subs': None,
            'vote_count': 0,
            'author': 'anonymous',
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

@app.route('/hash/<title>')
@jinja.template('search.html')
async def hash_search(request, title):
    hashcode = base64.b64decode(title)
    table = dynamodb.Table('Videos')
    db_query = table.scan(
        FilterExpression=Attr('hash').contains(hashcode),
        ConsistentRead=True
        )
    items = db_query['Items']
    extract_title = lambda x:x['title']
    extract_id = lambda x:x['id']
    extract_date = lambda x:x.get('upload_date')
    results = []
    for item in items:
        info = {}
        info.update({'title': extract_title(item)})
        info.update({'id' : extract_id(item)})
        info.update({'upload_date' : extract_date(item)})
        results.append(info)
    return {'results': results}

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
    extract_date = lambda x:x.get('upload_date')
    results = []
    for item in items:
        info = {}
        info.update({'title': extract_title(item)})
        info.update({'id' : extract_id(item)})
        info.update({'upload_date' : extract_date(item)})
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
    db_item = db_query.get('Item')
    if db_item is None:
        abort(404)
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
    if request['session'].get('vote') is not None:
        return response.json({'status': 'error', 'count': count_vote})
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

    table.update_item(
        Key= {'id': query_id},
        UpdateExpression = "SET vote_count=:count_vote",
        ExpressionAttributeValues={
            ':count_vote': count_vote
            }
    )
    request['session']['vote'] = True
    return response.json({'status': 'ok', 'count': count_vote})

@app.route('/milestone2')
async def milestone(request):
    return response.redirect('https://drive.google.com/open?id=1bVEeyqf3NGO7y332PS1Mbob6_EXEUA4o')

@app.route('/job_queue')
async def get_queue_length(request):
    queue_length = len(q)
    job = get_current_job(connection=redis_connection)
    return response.json({'status':'ok', 'queue_length':queue_length, 'current_job': job})

@app.route('/edit/<id>')
@jinja.template('edit.html')
async def sub_edit(request, id):
    table = dynamodb.Table('Videos')
    db_query = table.get_item(
        Key={'id':id},
        ConsistentRead=True
        )
    transcribe = Transcribe()
    db_item = db_query['Item']
    transcript = db_item['transcript']
    subtitles = transcribe.parse_to_edit(transcript)
    return {'subtitles': subtitles,\
    'vtt': 'trans{}.srt'.format(id),
    'id': id}

@app.route('/edit/temp', methods=['POST'])
async def interrim_vtt(request):
    variables = request.form
    srt = variables['id'][0]
    t = Transcribe()
    if request['session'].get('vtt') is None:
        request['session']['vtt'] = t.srt_to_vtt_mem(srt)
    curr_vtt = request['session']['vtt']
    curr_vtt = t.make_change_vtt(curr_vtt, start, end, text)
    request['session']['vtt'] = curr_vtt
    return response.json({
        'status':'ok',
        'uri': '/edit/vtt/{}.vtt'.format(srt)
        })


@app.route('/edit/vtt/<id>.vtt')
async def temp_vtt(request, id):
    curr_vtt = request['session']['vtt']
    return response.text(curr_vtt)

@app.route('/<srt>.vtt')
async def vtt(request, srt):
    t = Transcribe()
    return response.text(t.srt_to_vtt_mem(srt))


@app.exception(NotFound)
async def handle_404(request, exception):
    variables = {
        'error_url': request.path
        }
    return jinja.render('404.html',request, status=404, **variables)

@app.exception(ServerError)
async def handle_500(request, exception): 
    variables = {
        'exception': exception
        }
    return jinja.render('500.html',request, status=500, **variables)



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, workers=5, debug=True, access_log=True)
