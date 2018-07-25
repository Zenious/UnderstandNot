function goSearch() {
	var searchTerm = $('input[name="search"').val().trim();
	if (searchTerm != '') {
		$('#search-form').submit();
	}
}

function convert(value) {
    return Math.floor(value / 60) + ":" + (value % 60 ? value % 60 : '00')
}

function convert(value) {
	return Math.floor(value / 60) + ":" + (value % 60 ? value % 60 : '00')
}

function formatTime() {
  let time = $('#timeDuration').text();
  console.log(time);
  if (time == "") {
  	$('#timeDuration').html("Not available")
  } else {
	  let timeFormatted = convert(time);
	  $('#timeDuration').html(timeFormatted);
	}
};

function formatDate(secs) {
    var t = new Date(1970, 0, 1);
    t.setSeconds(secs);
    return t;
}

function getNewStats() {
	$.get( "/job_queue", function(data) {
  if (data.status == "ok") {
  	$('#queue-length').text(data.queue_length);
  	if (data.current_job == null) {
  		$('#current-job').text('Currently Not serving any Job!');
  	} else {
  		$('#current-job').text('Currently serving Job '+data.current_job);
  	}
  	$('#update').text(`Updated ${timeago().format(new Date())}`);
  } else {
  	$('#update').text('Update Failed!!!');
  }
})
  .fail(function() {
	$('#update').text('Update Failed!!!');
  });
	resizeFooter();
}

function resizeFooter() {
	$('main').css('margin-bottom', $('.footer').height());
}

function seekToTime(row) {
	const time = row.children[1].innerText;
	$('#edit-index').val(row.children[0].innerText);
	$('#edit-start').val(row.children[1].innerText);
	$('#edit-end').val(row.children[2].innerText);
	$('#edit-text').val(row.children[3].innerText);

	let player = videojs('my-video_html5_api');
	player.play();
	player.currentTime(parseInt(time));
	player.pause();
}
let test;
function applyChange(row) {
	let link = '';
	let payload = { 
		id: $(row [name='id']).val(),
		start: $(row [name='start']).val(),
		end: $(row [name='end']).val(),
		text: $(row [name='text']).val(),
		index: $(row [name='index']).val()
	 };
	let original = $(`#sub_${payload.index}`);
	test = original;
	originalData = original.children()
	originalData[1].innerHTML = payload.start;
	originalData[2].innerHTML = payload.end;
	originalData[3].innerHTML = payload.text;
	$.post("/edit/temp", payload,function( data ) {
	  console.log( data );
	  link = data.uri;

		let player = videojs('my-video_html5_api');
		let tracks = player.textTracks();
			tracks.tracks_.forEach(function(track) {
			if (track.label == 'edit') {
				tracks.removeTrack(track);
			}
		});
			console.log(link);
		let opts = {
			'src': link,
			'label': 'edit',
			'language': 'en'
		};
		let newTrack = player.addRemoteTextTrack(opts);
		tracks = player.textTracks();
		tracks.tracks_.forEach(function(track) {
			if (track.label == 'edit') {
				track.mode = 'showing';
			} else {
				track.mode = 'disabled';
			}
		});
		player.play();
		player.pause();
	  
	});
}

$(document).ready( function() {
	if ($('#file').length) {
		$('#file').change(function() {
			// Reject more than 100MB (cloudflare limit)
			if ($(this).prop('files')[0].size > 100*1024*1024) {
				alert('Upload file size limit is 100MB');
			}
		}) 
	}

	if ($('#timeDuration').length) {
		formatTime();
	};

	if ($('#queue-length').length) {
		getNewStats();
		setTimeout(getNewStats,5000)
	};
	if ($('.upload-date').length) {
		$(".upload-date").each(function() {
			let unformattedDate = $(this).html();
			if (unformattedDate == 'None') {
				$(this).html("Not Supported");
			} else {
				let formattedDate = formatDate(unformattedDate);
				$(this).html(formattedDate);
			} 
		});
	};


	resizeFooter();
	let didResize = false;

	$(window).resize(function() {
	  didResize = true;
	});
	
	setInterval(function() {
	  if(didResize) {
	    didResize = false;
	    resizeFooter();
	  }
	}, 250);

})
