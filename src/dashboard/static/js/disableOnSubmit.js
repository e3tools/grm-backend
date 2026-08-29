<!-- Disable button on submit -->

function disableOnSubmit(selector) {
    selector.find(":submit").attr('disabled', 'disabled');
    selector.find(".disabled-on-submit").addClass('disabled').attr('disabled', 'disabled');
    selector.find(".submit-spin").removeClass('d-none');
}

$(document).on("submit", "form", function () {
    disableOnSubmit($(this));
});

$(document).on("click", ".disabled-on-submit", function () {
    disableOnSubmit($("form"));
});

function enableOnSubmit() {
    $(".submit-spin").addClass('d-none');
}

function enableButton(selector) {
    selector.find(".disabled-on-submit").removeClass('disabled').removeAttr('disabled');
    selector.find(":submit").removeClass('disabled').removeAttr('disabled');
    selector.find(".submit-spin").addClass('d-none');
}

$(document).ready(function () {
    enableOnSubmit();

    $(document).on('click', '.disabled-on-submit', function () {
        $(this).attr('disabled', 'disabled');
        $(this).find(".submit-spin").removeClass('d-none');
    });
});