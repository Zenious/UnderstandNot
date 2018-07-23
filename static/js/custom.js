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
  let timeFormatted = convert(time);
  $('#timeDuration').html(timeFormatted);
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
  	$('#update').text('Updated on ??');
  } else {
  	$('#update').text('Update Failed!!!');
  }
})
  .fail(function() {
	$('#update').text('Update Failed!!!');
  })
}

function resizeFooter() {
	$('main').css('margin-bottom', $('.footer').height());
}

function seekToTime(row) {
	const time = row.children[1].innerText;
	$('#edit-start').val(row.children[1].innerText);
	$('#edit-end').val(row.children[2].innerText);
	$('#edit-text').val(row.children[3].innerText);

	let player = videojs('my-video_html5_api');
	player.play();
	player.currentTime(parseInt(time));
	player.pause();
}

function applyChange(row) {
	let link = '';
	$.post( "/edit/temp", { id: "transe40add59a4f6478cb1b83d661cc2714b.srt" },function( data ) {
	  console.log( data );
	  link = data.uri;
	  
	});
	let player = videojs('my-video_html5_api');
	let tracks = player.textTracks();
		tracks.tracks_.forEach(function(track) {
		if (track.label == 'edit') {
			tracks.removeTrack(track);
		}
	});
	let opts = {
		'src': 'http://localhost:8000/r/transe40add59a4f6478cb1b83d661cc2714b.srt.vtt',
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
		console.log('change is good');

}

$(document).ready( function() {
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
