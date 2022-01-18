
var apiBaseUrl = document.currentScript.dataset.apiBaseUrl
function selectizeDeviceInput(){
    $("select[name='device']").selectize({
        valueField: 'id',
        labelField: 'device_id',
        searchField: 'device_id',
        multiple: true,
        create: false,
        plugins: [ 'preserve_on_blur' ],
        load: function(query, callback) {
            if (!query.length || query.length < 4) {
              return callback()
            }
            $.ajax({
                url: apiBaseUrl + 'search/device?q=' + encodeURIComponent(query),
                type: 'GET',
                error: function() {
                    callback()
                },
                success: function(res) {
                    callback(res.results)
                }
            })
        }
    })
}

$(function() {
    $('.date-utc').each(function(i, el){
        $el = $(el)
        $el.text(dayjs($el.data('date')).local().format('MMMM D, YYYY [at] HH:mm:ss'))
    })
    selectizeDeviceInput()
})
