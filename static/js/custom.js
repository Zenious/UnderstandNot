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

$(document).ready( function() {
	formatTime();
})