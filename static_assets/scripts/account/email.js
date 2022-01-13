(function() {
    var message = 'Do you really want to remove the selected e-mail address?';
    var actions = document.getElementsByName('action_remove');
    if (actions.length) {
      actions[0].addEventListener("click", function confirmRemove(e) {
        e.preventDefault();
        swal(
          {
            title: 'Confirm',
            text: message,
            type: 'warning',
            confirmButtonText: 'Delete',
            showCancelButton: true,
            confirmButtonClass: "btn-danger",
          },
          function(isConfirmed){
            if(isConfirmed){
              actions[0].removeEventListener('click', confirmRemove)
              actions[0].click();
            }
          }
        );
      });
    }
  })();
