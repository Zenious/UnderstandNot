function goSearch() {
	var searchTerm = $('input[name="search"').val().trim();
	if (searchTerm != '') {
		$('#search-form').submit();
	}
}