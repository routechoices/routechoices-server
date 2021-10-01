$(function() {
  $('.error-message').hide();
  $('#imeiForm').on('submit', function(e) {
    e.preventDefault();
    $('#imeiRes').text($('#IMEI').val())
    $.ajax({
      type: 'POST',
      url: '/api/imei/',
      dataType: 'json',
      data: {imei: $('#IMEI').val()}
    }).done(function(response) {
      $('#IMEIDiv').removeClass('is-invalid')
      $('#imeiDevId').removeClass('d-none')
      $('.imeiDevId').text(response.device_id);
      $('#imeiErrorMsg').addClass('d-none');
    }).fail(function() {
      $('#imeiErrorMsg').removeClass('d-none');
      $('#IMEI').addClass('is-invalid')
      $('#imeiDevId').addClass('d-none')
    })
  })
});