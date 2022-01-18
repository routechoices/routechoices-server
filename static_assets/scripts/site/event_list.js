(function(){
  u('.date-utc').each(function(el){
      $el = u(el)
      $el.text(dayjs($el.data('date')).local().format('YYYY-MM-DD HH:mm:ss'))
  })
})()
