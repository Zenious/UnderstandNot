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


$(document).ready( function() {
	if ($('#timeDuration').length) {
		formatTime();
	};

	if ($('#queue-length').length) {
		getNewStats();
		setTimeout(getNewStats,5000)
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
