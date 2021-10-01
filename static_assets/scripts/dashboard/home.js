$(function () {
    var offset = moment().utcOffset();
    var offsetText = (offset > 0 ? '+' : '-') +
        ('0' + Math.floor(Math.abs(offset / 60))).slice(-2) + ':' +
        ('0' + Math.round(offset % 60)).slice(-2);
    $('.utc-offset').text('(UTC Offset ' + offsetText + ')');
    $('[data-toggle="offcanvas"]').on('click', function () {
        $('.row-offcanvas').toggleClass('active')
    });
});