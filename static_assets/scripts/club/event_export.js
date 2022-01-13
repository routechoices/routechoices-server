
$(function(){
    $('.date-utc').each(function(i, el){
        $el = $(el);
        $el.text(dayjs($el.data('date')).local().format('YYYY-MM-DD HH:mm:ss'));
    });
})
