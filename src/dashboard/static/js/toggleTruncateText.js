$(document).on('click', '.truncate', function () {
    let fullText = $(this).attr('data-full-text');

    if ($(this).hasClass('expanded')) {
        $(this).removeClass('expanded');
        $(this).html(fullText.substring(0, 100) + '...');
    } else {
        $(this).addClass('expanded');
        $(this).html(fullText);
    }
});
