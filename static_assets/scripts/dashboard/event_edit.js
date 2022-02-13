
var apiBaseUrl = document.currentScript.dataset.apiBaseUrl

var seletizeOptions = {
    valueField: 'id',
    labelField: 'device_id',
    searchField: 'device_id',
    create: false,
    plugins: [ 'preserve_on_blur' ],
    load: function(query, callback) {
        if (!query.length || query.length < 4) return callback()
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
}

function onAddedCompetitorRow(row) {
    var options = {
        useCurrent: false,
        display: {
        components: {
            useTwentyfourHour: true,
            seconds: true,
        }
        }
    }
    var el = $(row).find('.datetimepicker')[0]
    new tempusDominus.TempusDominus(el, options)
    $(row).find('select[name$="-device"]').selectize(seletizeOptions)
}

function onCsvParsed(result){
    document.getElementById("csv_input").value = ""
    var errors = ""
    if (result.errors.length>0) {
        errors = "No line found"
    }
    if(!errors) {
        result.data.forEach(function(l){
            var empty = false
            if(l.length==1 && l[0] == "") {
                empty = true
            }
            if(!empty && l.length != 4) {
                errors = "Each row should have 4 columns"
            } else {
                if(!empty && l[2]){
                    try {
                      new Date(l[2])
                    } catch (e) {
                      errors = "One row contains an invalid date"
                    }
                }
            }
        })
    }
    if(errors){
        swal({
            title: 'Error!',
            text: 'Could not parse this file: ' + errors,
            type: 'error',
            confirmButtonText: 'OK'
        })
        return
    }
    // clear empty lines
    $('.formset_row').each(function(j, e){
        if($(e).find('input').filter(
            function(i, el){
                return $(el).attr('type')!='hidden' && el.value != ''
            }).length == 0) {
            $(e).find('.delete-row').click()
        }
    })
    result.data.forEach(function(l) {
        $('.add-competitor-btn').click()
        if(l.length!=1) {
            var inputs = $('.formset_row').last().find('input')
            if (l.length > 3) {
                inputs[2].value = l[3]
            }
            inputs[3].value = l[0]
            inputs[4].value = l[1]
            inputs[5].value = l[2]
        }
    })
    $('.add-competitor-btn').click()
}

function showLocalTime(el) {
    var val = $(el).val()
    if (val) {
        var local = dayjs(val).utc(true).local().format('YYYY-MM-DD HH:mm:ss')
        $(el).parent().find('.local_time').text(local + ' Local time')
    } else {
        $(el).parent().find('.local_time').text('')
    }
}

$(function(){
    $('.datetimepicker').map(function(i, el) {
        var options = {
            useCurrent: false,
            display: {
            components: {
                useTwentyfourHour: true,
                seconds: true,
            }
            }
        }
        $el = $(el)
        var val = $el.val()
        if(val) {
        val = val.substring(0,10) + 'T' + val.substring(11, 19) + 'Z'
        options.defaultDate = new Date(new Date(val).toLocaleString('en-US', { timeZone: "UTC" }))
        }
        new tempusDominus.TempusDominus(el, options)
    })
    $('label[for$="-DELETE"]').parents('.form-group').hide()
    $('.formset_row').formset({
        addText: '<i class="fa fa-plus-circle"></i> Add Competitor',
        addCssClass: 'btn btn-primary add-competitor-btn',
        deleteText: '<i class="fa fa-trash fa-2x"></i>',
        prefix: 'competitors',
        added: onAddedCompetitorRow
    })
    $('.extra_map_formset_row').formset({
        addText: '<i class="fa fa-plus-circle"></i> Add Map',
        addCssClass: 'btn btn-primary add-map-btn',
        deleteText: '<i class="fa fa-trash fa-2x"></i>',
        prefix: 'map_assignations',
        formCssClass: 'extra_map_formset_row',
    })
    // next line must come after formset initialization
    $('select[name$="-device"]').selectize(seletizeOptions)

    var originalEventStart = $('#id_start_date').val()
    var competitorsWithSameStartAsEvents = $('.competitor_table .datetimepicker').filter(function(idx, el){
        return originalEventStart !== '' && $(el).val() == originalEventStart
    }).map(function(idx, el){
        return $(el).attr('id')
    }).toArray()

    $('#csv_input').on('change', function(){
        Papa.parse($('#csv_input')[0].files[0], {complete: onCsvParsed})
    })
    $('.datetimepicker').each(function(idx, el){
        $(el).attr("autocomplete", "off")
        showLocalTime(el)
        el.addEventListener(tempusDominus.Namespace.events.change, function(e) {
            var elId = $(e.target).attr('id')
            if (competitorsWithSameStartAsEvents.includes(elId)) {
                const index = competitorsWithSameStartAsEvents.indexOf(elId)
                if (index > -1) {
                    competitorsWithSameStartAsEvents.splice(index, 1)
                }
            }
            showLocalTime(e.target)
        })
    })

    var utcOffset = dayjs().utcOffset()
    var utcOffsetText = (utcOffset > 0 ? '+' : '-') +
        ('0' + Math.floor(Math.abs(utcOffset / 60))).slice(-2) + ':' +
        ('0' + Math.round(utcOffset % 60)).slice(-2)
    $('.utc-offset').text('(UTC Offset ' + utcOffsetText + ')')

    document.getElementById('id_start_date').addEventListener(tempusDominus.Namespace.events.change, function(e) {
        var newValue = $(e.target).val()
        $(competitorsWithSameStartAsEvents).each(function(idx, id){
            $('#'+id).val(newValue)
        })
    })
})
