var apiBaseUrl = document.currentScript.dataset.apiBaseUrl

$('#id_device').selectize({
    valueField: 'id',
    labelField: 'device_id',
    searchField: 'device_id',
    multiple: true,
    create: false,
    plugins: [ 'preserve_on_blur' ],
    load: function(query, callback) {
        if (!query.length || query.length < 4) return callback();
        $.ajax({
            url: apiBaseUrl + 'device/search?q=' + encodeURIComponent(query),
            type: 'GET',
            error: function() {
                callback();
            },
            success: function(res) {
                callback(res.results);
            }
        });
    }
});
