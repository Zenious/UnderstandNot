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
from hashlib import md5, pbkdf2_hmac
import json
from boto3.dynamodb.conditions import Attr
import time
from sanic.exceptions import NotFound, ServerError, abort
from sanic.log import logger as log
import base64
from sanic_session import RedisSessionInterface
import configparser
import os
import asyncio_redis
from elasticsearch import Elasticsearch
import certifi

class Redis_pool:
    """
    A simple wrapper class that allows you to share a connection
    pool across your application.
    """
    _pool = None

    async def get_redis_pool(self):
        if not self._pool:
            self._pool = await asyncio_redis.Pool.create(
                host='localhost', port=6379, poolsize=10
            )

        return self._pool

config = configparser.ConfigParser()
config.read('config.ini')
app = Sanic()
app.config.REQUEST_MAX_SIZE = 100*1024*1024 # 100MB
app.static('/r', './resources')
app.static('/static', './static')

jinja = SanicJinja2(app)
redis_connection = Redis()
q = Queue(connection=redis_connection)
dynamodb = boto3.resource('dynamodb')

redis = Redis_pool()
# pass the getter method for the connection pool into the session
session_interface = RedisSessionInterface(redis.get_redis_pool)

es = Elasticsearch([config['ELASTICSEARCH']['HOST']], use_ssl=True, ca_certs=certifi.where())

@app.middleware('request')
async def add_session_to_request(request):
    # before each request initialize a session
    # using the client's request
    await session_interface.open(request)


@app.middleware('response')
async def save_session(request, response):
    # after each request save the session,
    # pass the response to set client cookies
    await session_interface.save(request, response)


@app.route('/')
@jinja.template('index.html')
async def index(request):
    return

@app.route('/about')
@jinja.template('about.html')
async def about(request):
    return

@app.route('/contact')
@jinja.template('contact.html')
async def contact(request):
    return

@app.route('/tou')
@jinja.template('tou.html')
async def tou(request):
    return

@app.route('/privacy')
@jinja.template('privacy.html')
async def privacy(request):
    return


@app.route('/upload', methods=['GET', 'POST'])
async def post_upload(request):
    if request.method == 'GET':
        return abort(404)

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

        b64hash = base64.b64encode(hashcode).decode("ascii")
        es_search = es.search(index='videos', body={
            "query": {
                "match": {
                    "hash": b64hash
                    }
                }
            })
        if es_search['hits']['total'] > 0:
            # check if truly have hash
            es_record_found = es_search['hits']['hits']
            for record in es_record_found:
                if record['_source']['hash'] == b64hash:
                    # found 1 is enough
                    return response.redirect('/hash/{}'.format(b64hash))
            # if cannot find, continue to create new job

        table = dynamodb.Table('Videos')
        table.put_item(Item={
            'id': index,
            'title': file_name,
            'hash': hashcode,
            'job_status': 'Queue for Audio Extraction',
            'transcript': None,
            'subs': None,
            'link': index,
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

@app.route('/parse', methods=['GET', 'POST'])
async def post_transcribe(request):
    if request.method == 'GET':
        return abort(404)
    Transcribe.parseOutput()
    return response.text("TODO")

@app.route('/search')
async def search_redirect(request):
    inputs = request.args
    if len(inputs) < 1:
        abort(404)
    return response.redirect('/search/{}'.format(inputs['search'][0]))

@app.route('/hash/<title>')
@jinja.template('search.html')
async def hash_search(request, title):
    try:
        es_search = es.search(index='videos', body={
                "query": {
                    "match": {
                        "hash": title
                        }
                    }
                })
        records = es_search['hits']['hits']
        results = []
        for record in records:
            info = {}
            info['id'] = record['_id'][3:] # remove prefix of 'id='
            record_info = record['_source']
            if record_info['hash'] != title:
                pass
            terms = ['upload_date', 'title', 'author']
            for term in terms:
                info[term] = record_info[term]
            results.append(info)
        return {'results': results}
    except:
        abort(404)

@app.route('/search/<title>')
@jinja.template('search.html')
async def search(request, title):
    # get GET Parameters

    jinja_response = {}
    jinja_response.update({'search_query': title});
    es_search = es.search(index='videos', body={
            "query": {
                "match": {
                    "title": title
                    }
                }
            })
    records = es_search['hits']['hits']
    results = []
    for record in records:
        info = {}
        info['id'] = record['_id'][3:] # remove prefix of 'id='
        record_info = record['_source']
        terms = ['upload_date', 'title', 'author']
        for term in terms:
            info[term] = record_info[term]
        results.append(info)

    jinja_response.update({'results': results})
    return jinja_response


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
    timestamp = {'date': db_item['upload_date']}
    author = {'author': db_item['author']}
    count = db_item.get('vote_count')
    if count is None:
        count = 0
    jinja_response.update({'status': job_status})
    jinja_response.update(title)
    jinja_response.update(timestamp)
    jinja_response.update(author)
    try:
        duration = {'duration': db_item['video_length']}
        jinja_response.update(duration)
    except:
        pass

    if job_status == 'Sent Audio For Transcription':
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
            srt_mem = trans.srt_mem(trans_file+'.srt')
            table = dynamodb.Table('Videos')
            trans_data = {}
            with open(trans_file, "r") as f:
                trans_data = json.load(f)
            # Delete transcription file
            try:
                os.remove(trans_file)
            except OSError:
                pass
            # Delete srt file in disk
            try:
                os.remove('./resources/{}'.format(path_file))
            except OSError:
                pass
            # Delete audio file in S3 bucket
            s3 = boto3.client('s3')
            bucket='orbitalphase1'
            audio_file = './resources/{}.flac'.format(id)
            s3.delete_object(Bucket=bucket, Key=audio_file)

            table.update_item(
                Key= {'id': id},
                UpdateExpression = "SET job_status=:job_status, subs=:subtitles, transcript=:transcript",
                ExpressionAttributeValues={
                    ':job_status': 'Transcription done',
                    ':transcript': trans_data,
                    ':subtitles': srt_mem
                    }
                )
            jinja_response.update({'status': status})
            jinja_response.update({'srt': id, 'flac': id, 'ready': True, 'count': count})
            return jinja_response
        elif status == 'IN_PROGRESS':
            status= 'Sent to AWS to Transcribe'
            jinja_response.update({'status': status})
            return jinja_response
        else:
            return jinja_response
    elif job_status == 'Transcription done' or "Edited" in job_status :
        jinja_response.update({
            'flac': id,
            'srt': id,
            'ready': True,
            'count': count
            })
        return jinja_response
    else:
        return jinja_response


@app.route('/video/<id>')
@jinja.template('video.html')
async def video(request, id):
    table = dynamodb.Table('Videos')
    jinja_response = {}
    db_query = table.get_item(
        Key={'id':id},
        ConsistentRead=True
    )
    if db_query.get('Item') is None:
        abort(404)
    item = db_query['Item']
    try:
        jinja_response.update({'vtt': id})
        jinja_response.update({'id': id})
        jinja_response.update({'video': item['link']})
        jinja_response.update({'title': item['title']})
        jinja_response.update({'author': item['author']})
    except:
        abort(404)

    return jinja_response

@app.route('/vote')
async def vote(request):
    try:
        args = request.args
        query_id = args.get('id')
        query_vote = args.get('vote')
        table = dynamodb.Table('Videos')
        db_query = table.get_item(
            Key={'id':query_id},
            ConsistentRead=True
        )
        item = db_query['Item']
        count_vote = item.get('vote_count')
        if count_vote is None:
            count_vote = 0
        voting_status = request['session'].get('vote')
        if voting_status:
            voted = request['session']['vote']
            log.info(type(voted))
            if query_id in voted:
                return response.json({'status': 'error', 'count': count_vote})
        else:
            voted = []
        if query_vote == 'yes':
            count_vote += 1
        else:
            count_vote -= 1
        voted.append(query_id)
        table.update_item(
            Key= {'id': query_id},
            UpdateExpression = "SET vote_count=:count_vote",
            ExpressionAttributeValues={
            ':count_vote': count_vote
            }
        )

        request['session']['vote'] = voted
        return response.json({'status': 'ok', 'count': count_vote})
    except:
        abort(404)

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
    try:
        jinja_response = {}
        table = dynamodb.Table('Videos')
        db_query = table.get_item(
            Key={'id':id},
            ConsistentRead=True
            )
        transcribe = Transcribe()
        db_item = db_query['Item']
        subtitle = transcribe.srt_to_edit(db_item['subs'])
        request['session']['vtt'] = transcribe.srt_mem_to_vtt_mem(db_item['subs'])
        jinja_response.update({'subtitles': subtitle})
        jinja_response.update({'vtt': '{}'.format(id)})
        jinja_response.update({'id': id})
        jinja_response.update({'video': db_item['link']})

        return jinja_response
    except:
        abort(404)

@app.route('/edit/temp', methods=['GET', 'POST'])
async def interrim_vtt(request):
    if request.method == 'GET':
        return abort(404)

    variables = request.form
    srt = variables['id'][0]
    start = variables['start'][0]
    end = variables['end'][0]
    text = variables['text'][0]
    index = int(variables['index'][0])
    t = Transcribe()
    if request['session'].get('vtt') is None:
        table = dynamodb.Table('Videos')
        db_query = table.get_item(
            Key={'id':srt},
            ConsistentRead=True
            )
        item = db_query.get('Item')
        request['session']['vtt'] = t.srt_mem_to_vtt_mem(item['subs'])
    curr_vtt = request['session']['vtt']
    curr_vtt = t.make_change_vtt(curr_vtt, index, start, end, text)
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
    table = dynamodb.Table('Videos')
    db_query = table.get_item(
        Key={'id':srt},
        ConsistentRead=True
        )
    item = db_query.get('Item')
    if item is None:
        abort(404)
    return response.text(t.srt_mem_to_vtt_mem(item['subs']))

@app.route('/<uid>.srt')
async def srt(request, uid):
    table = dynamodb.Table('Videos')
    db_query = table.get_item(
        Key={'id':uid},
        ConsistentRead=True
        )
    item = db_query.get('Item')
    if item is None:
        abort(404)
    return response.text(item['subs'])

@app.route('/edit/commit', methods=['GET','POST'])
async def commit_change(request):
    if request.method == 'GET':
        abort(404)

    curr_vtt = request['session']['vtt']
    transcribe = Transcribe()
    new_srt = transcribe.vtt_mem_to_srt(curr_vtt)

    variables = request.form
    id = variables['id'][0]
    author = variables['author'][0]
    index = uuid.uuid4().hex

    table = dynamodb.Table('Videos')
    db_query = table.get_item(
        Key={'id':id},
        ConsistentRead=True
        )
    db_item = db_query.get('Item')
    new_item = {}
    for k,v in db_item.items():
        new_item[k] = v
    new_item['id'] = index
    new_item['author'] = author
    new_item['upload_date'] = int(time.time())
    new_item['job_status'] = 'Edited from <a href="{}">{}</a>'.format(id, id)
    new_item['vote_count'] = 0
    new_item['subs'] = new_srt

    table.put_item(Item=new_item)

    return response.redirect('/job/{}'.format(index))

@app.route('/UnderstandLiao', methods=['GET', 'POST'])
async def admin_panel(request):
    if request.method == 'GET':
        if request['session'].get('admin') is not True:
            return jinja.render('login.html', request=request)
        else:
            es_search = es.search(
                index="videos",
                body={
                    "query": {
                        'match_all' : {}
                        }
                    }
                )
            records = es_search['hits']['hits']
            results = []
            for record in records:
                info = {}
                info['id'] = record['_id'][3:] # remove prefix of 'id='
                record_info = record['_source']
                terms = ['upload_date', 'title', 'author']
                for term in terms:
                    info[term] = record_info[term]
                results.append(info)
            variables = {
                'admin' : True,
                'results': results}
            return jinja.render('search.html', request=request, **variables)
    elif request.method == 'POST':
        inputs = request.form
        user = inputs['user'][0]
        pw = inputs['password'][0]
        bpw = pw.encode('utf-8')
        hashedpw = pbkdf2_hmac('sha256', bpw, config['DB']['SALT'].encode('utf-8'), 100000)
        table = dynamodb.Table('Admin')
        db_query = table.get_item(Key={
            'user':user,
            },
            ConsistentRead=True)
        if db_query.get('Item') is None:
            abort(403)
        else:
            if hashedpw == db_query.get('Item')['password']:
                request['session']['admin'] = True
                return response.redirect('/UnderstandLiao')
            else:
                abort(403)

    else:
        abort(403)

@app.route('/delete', methods=['GET', 'POST'])
async def delete_job(request):
    if request.method == 'GET':
        abort(404)

    if request['session'].get('admin') is not True:
        return response.redirect('/UnderstandLiao')
    else:
        inputs = request.form
        id = inputs['id'][0]
        table = dynamodb.Table('Videos')
        table.delete_item(
            Key={
                'id': id
            }
        )
        # Delete video file
        try:
            os.remove('./resources/{}'.format(id))
        except OSError:
            pass
        # Delete srt file
        try:
            os.remove('./resources/trans{}.srt'.format(id))
        except OSError:
            pass
        return response.redirect('/UnderstandLiao')

@app.exception(NotFound)
async def handle_404(request, exception):
    variables = {
        'error_url': request.path
        }
    return jinja.render('404.html',request, status=404, **variables)

# @app.exce '500.html',request, status=500, **variables)


if __name__ == '__main__':
    if config['GENERAL']['STATUS'] == 'dev':
        app.run(host='0.0.0.0', port=8000, workers=5, debug=True, access_log=True)
    else :
        ssl = {'cert': config['SSL']['CERT'], 'key': config['SSL']['PRIVATE_KEY']}
        app.run(host='0.0.0.0', port=8000, workers=5, debug=True, access_log=True, ssl=ssl)
