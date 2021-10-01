
var extractCornersCoordsFromFilename = function(filename) {
    var re = /(_\d+\.\d+){8}_\.(gif|png|jpg|jpeg)$/ig
    var found = filename.match(re)
    if(!found) {
        return false
    } else {
        var coords = found[0].split('_')
        coords.pop()
        coords.shift()
        return coords.join(',')
    }
}
$(function(){
    $('#id_image').on('change', function(){
        if(this.files[0].size > 1e7){
            swal({
                title: 'Error!',
                text: 'File is too big!',
                type: 'error',
                confirmButtonText: 'OK'
            });
            this.value = ""
        }
        if(this.value) {
            var bounds = extractCornersCoordsFromFilename(this.files[0].name)
            if (bounds && !$('#id_corners_coordinates').val()) {
                $('#id_corners_coordinates').val(bounds)
            }
            $('#calibration_help').removeClass('hidden')
        } else {
            $('#calibration_help').addClass('hidden')
        }
    });
})