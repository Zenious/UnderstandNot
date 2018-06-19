from sanic import Sanic
from sanic import response
from extractAudio import AudioExtract
from readJSON import Transcribe
app = Sanic()
app.static('/static', '.')

@app.route('/')
async def test(request):
    return response.html('''<!doctype html>
    <title>Upload new File</title>
    <h1>Upload new File</h1>
    <form action="upload" method=post enctype=multipart/form-data>
      <input type=file name=file>
      <input type=submit value=Upload>
    </form>   
    <h1>Upload new JSON</h1>
    <form action="parse" method=post enctype=multipart/form-data>
      <input type=file name=file>
      <input type=submit value=Upload>
    </form>
        ''')


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

        create_file(file_name, file_body)
        # TODO upload video to S3 Bucket
        audio_file = AudioExtract.extractFLAC(file_name)
        # TODO upload audio to S3 Bucket
        # TODO send req to transcribe
        return response.html('''<!DOCTYPE html>
<html>
<body>

<audio controls>
  <source src="/static/{}" type="audio/flac">
Your browser does not support the audio element.
</audio>
</body>
</html>

            '''.format(audio_file))
    else:
        create_file(file_name, file_body)
        trans = Transcribe()
        trans.parseOutput(file_name)
        return response.text(file_type)
    # if file.filename == '':
    #     return response.text('no filename')
    # return response.text('got found')

def create_file(filename, data):
    f = open(filename, 'wb')
    f.write(data)
    f.close()

@app.route('/parse', methods=['POST'])
async def post_transcribe(request):
    Transcribe.parseOutput()
    return response.text("TODO")
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)