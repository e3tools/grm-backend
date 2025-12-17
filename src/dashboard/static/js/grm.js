<!-- Constants -->
const error_server_message = "An error has occurred, please check your network connection and try again. ";
const server_error_html_alert = createHtmlAlert(error_server_message);

<!-- Django messages -->
/**
 * Show alerts and hide success alerts after 4 seconds
 */

$(".alert-div-content").fadeIn();
window.setTimeout(function () {
    $(".alert-success").fadeOut();
}, 4000);

// alerts displayed in modal
$(".messageModal").modal("show");
window.setTimeout(function () {
    $(".modal-success").modal("hide");
}, 4000);

// It is used to show the alerts from an ajax call
function showPopupMessage(responseJSON) {
    let content;
    let response = 'success'
    if (responseJSON && typeof responseJSON === "object" && 'msg' in responseJSON) {
        content = responseJSON.msg;
    } else {
        content = server_error_html_alert;
    }
    if (content.includes("alert-danger")) {
        window.scrollTo({top: 0, behavior: 'smooth'});
        response = 'error';
    }
    let messages = $('#popup-messages-content');
    if (messages.length && content) {
        messages.html(content);
    }
    $(".alert-div-content").fadeIn();
    window.setTimeout(function () {
        $(".alert-success").fadeOut();
    }, 4000);

    $(".messageModal").show();
    window.setTimeout(function () {
        $(".modal-success").hide();
    }, 4000);

    $('.close').click(function () {
        $(this).closest('.alert').fadeOut();
    });
    return response;
}

$('.form-check').addClass("icheck-primary");

function delay(callback, ms) {
    let timer = 0;
    return function () {
        let context = this, args = arguments;
        clearTimeout(timer);
        timer = setTimeout(function () {
            callback.apply(context, args);
        }, ms || 0);
    };
}

function createHtmlAlert(msg) {
    return `<div class="row">
                <div class="col-md-12">
                    <div class="alert alert-danger">
                    <button type="button" class="close" data-dismiss="alert" aria-hidden="true">×</button>
                        ${msg}
                    </div>
                </div>
            </div>`
}