$(function(){
    $('#id_file').attr('accept', '.kml, .kmz')
    $('#id_file').on('change', function(){
        if(this.files[0].size > 1e7){
            swal({
                title: 'Error!',
                text: 'File is too big!',
                type: 'error',
                confirmButtonText: 'OK'
            });
            this.value = ""
        }
    })
})