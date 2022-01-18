(function () {
    document.querySelectorAll('[data-toggle="offcanvas"]').addEventListener('click', function () {
      [].slice.call(document.getElementsByClassName('row-offcanvas')).map(function(el){el.classList.toggle('active')})
    })
})()
