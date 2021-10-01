$(function(){
    $('#id_gpx_file').attr('accept', '.gpx')
    $('#id_gpx_file').on('change', function(){
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