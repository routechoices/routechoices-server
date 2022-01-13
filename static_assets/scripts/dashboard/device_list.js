
$(function(){
    $('.date-utc').each(function(i, el){
        var $el = $(el);
        $el.text(dayjs($el.data('date')).local().format('YYYY-MM-DD HH:mm:ss'));
    });
    $('.copy-btn').on('click', function(ev){
        var $el = $(ev.currentTarget)
        var tooltip = new bootstrap.Tooltip(ev.currentTarget,
            {'placement': 'right', 'title': 'copied'}
        )
        tooltip.show()
        setTimeout(function(){tooltip.dispose()}, 500)
        navigator.clipboard.writeText($el.data('value'))
    })
})
