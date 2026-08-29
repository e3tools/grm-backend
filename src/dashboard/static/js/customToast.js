function showToast(type = "danger", toast_title = undefined, toast_message=undefined) {
    // Clone the template
    let $toast = $("#toast-template").clone();
    $toast.removeAttr("id"); // avoid duplicates
    if (toast_title){
        $toast.find(".mr-auto").text(toast_title);
    }
    if (toast_message){
        $toast.find(".toast-body").text(message);
    }

    // Add color according to type
    if (type === "success") $toast.addClass("bg-success");
    else if (type === "info") $toast.addClass("bg-info");
    else if (type === "warning") $toast.addClass("bg-warning");
    else $toast.addClass("bg-danger");

    // Insert and display
    $("#toast-container").append($toast);
    $toast.toast("show");

    // Remove when finished
    $toast.on("hidden.bs.toast", function () {
        $(this).remove();
    });
}
