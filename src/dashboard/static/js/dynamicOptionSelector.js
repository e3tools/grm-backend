function loadData(url = '', data = {}, container = '', htmlOrValue = true) {
    $.ajax({                       // initialize an AJAX request
        url: url,                  // set the url of the request (= localhost:8000/hr/ajax/load-cities/)
        data: data,
        success: function (data) { // `data` is the return of the `load_cities` view function
          // replace the contents of the city input with the data that came from the server
          if(htmlOrValue == true) {
            $("#" + container).html(data);
          } else {
          console.log('write value in input field');
            $("#" + container).val(data);
          }
        }
    });
}