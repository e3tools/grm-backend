// Form management ---------------------------------------------------

function updateStepParam(step) {
    const url = new URL(window.location.href);

    // Update or add the 'step' parameter
    url.searchParams.set('step', step);

    // Change the URL without reloading the page
    window.history.pushState({}, '', url.toString());
}

function initSelect2(element) {
    if (!element.hasClass("select2-hidden-accessible")) {
        let options = {
            placeholder: element.attr("placeholder") || "",
            allowClear: true
        };

        // If the element is writable, allow custom tags
        if (element.hasClass("writable")) {
            options.tags = true;
        }

        element.select2(options);
    }
}

// When new content arrives via AJAX
$(document).ajaxSuccess(function () {
    $(document).find("form select").each(function () {
        initSelect2($(this));
    });
});

function submitForm($this, url, step, data) {
    $('#popup-messages-content').html('');
    $.ajax({
        type: "post",
        url: url,
        data: data,
        cache: false,
        processData: false,
        contentType: false,
        success: function (response) {
            $("#formAjax").html(response);

            showCheckedToDelete();

            if (response.includes("alert-danger")) {
                setTimeout(function () {
                    const firstError = document.querySelector('.alert-danger');
                    if (firstError) {
                        firstError.scrollIntoView({behavior: 'smooth', block: 'start'});
                    }
                }, 50);
            }
            if ($(response).find('.is-invalid').length === 0 && $(response).find('.errorlist').length === 0) {
                loadWizardSections(Number(step) + 1);
            }
        },
        error: function () {
            alert(error_server_message);
            enableButton($this);
        },
        complete: function () {
            wizard_sections_spin.hide();
        }
    });
}

$(document).on("click", ".timeline-item.pointer", function () {
    $('#popup-messages-content').html('');
    $(".timeline-item.pointer").removeClass("active");
    $(this).addClass("active");
    loadWizardSectionForm($('#formAjax'));
});

$(document).on("click", "#previous_step", function () {
    $('#popup-messages-content').html('');
    $(".timeline-item.pointer").removeClass("active");
    let previous_step = $(this).data("step") - 1;
    $("#" + previous_step).addClass("active");
    loadWizardSectionForm($('#formAjax'));
});

// Upload regions file management ---------------------------------------------

$(document).on("submit", "#formUploadModal", function (e) {
    e.preventDefault();
    let $this = $(this);
    let url = $this.attr("action");
    $.ajax({
        type: "post",
        url: url,
        data: new FormData($("#formUploadModal").get(0)),
        cache: false,
        processData: false,
        contentType: false,
        success: function (response) {
            if ($(response).find('.is-invalid').length > 0 || $(response).find('.errorlist').length > 0) {
                $("#uploadModal .modal-content").html($(response).find(".modal-content").html());
            } else {
                $("#uploadModal").modal('hide');
                let step = $(".timeline-item.active").attr("id");
                loadWizardSections(step);
                showPopupMessage(response.msg);
            }
        },
        error: function () {
            alert(error_server_message);
            enableButton($this);
        },
        complete: function () {
            wizard_sections_spin.hide();
        }
    });
});

// Next Step ---------------------------------------------

function submitNexStep($this, url) {
    $('#popup-messages-content').html('');
    $.ajax({
        type: "post",
        url: url,
        cache: false,
        processData: false,
        contentType: false,
        success: function (response) {
            $(".timeline-item.pointer").removeClass("active");
            let step = response.step;
            $("#" + step).addClass("active");
            loadWizardSections(response.step);
        },
        error: function () {
            alert(error_server_message);
            $this.removeClass('disabled').removeAttr('disabled');
            enableButton($("form"));
        },
        complete: function () {
            wizard_sections_spin.hide();
        }
    });
}

// Formset management ---------------------------------------------------

// Add new form
$(document).on('click', '#add-more', function () {
    if (formIndex >= maxForms) {
        $('#max-forms-alert').removeClass('d-none');
        return;
    }

    // Clone the empty form template
    let newForm = $('#empty-form-template').html();

    // Replace __prefix__ with the current form index
    newForm = newForm.replace(/__prefix__/g, formIndex);

    // Update data-form-index
    let $newForm = $(newForm);
    $newForm.attr('data-form-index', formIndex);

    // Add to container
    $('#formset-container').append($newForm);

    // Update form count
    formIndex++;
    $('#id_form-TOTAL_FORMS').val(formIndex);

    // Focus on the new input
    $newForm.find('input[type="text"]').focus();

    // Initialize select2 only for the selects of the new form
    $newForm.find('select').each(function () {
        initSelect2($(this));
    });
});

// Remove form (for new forms without instance.pk)
$(document).on('click', '.remove-row', function () {
    let $row = $(this).closest('.formset-row');

    // If there are select2 instances inside this row, destroy them to avoid leaks
    $row.find('select').each(function () {
        let $s = $(this);
        if ($s.hasClass('select2-hidden-accessible')) {
            $s.select2('destroy');
        }
    });

    $row.remove();

    // Update form indices and total count (this will re-init select2)
    updateFormIndices();

    // Hide alert
    $('#max-forms-alert').addClass('d-none');
});

$(document).on("click", ".restricted-deletion", function () {
    showToast();
});

// Show the forms to be deleted
function showCheckedToDelete() {
    $('[name$="-DELETE"]').each(function () {
        const $checkbox = $(this);
        if ($checkbox.prop('checked')) {
            const $container = $checkbox.closest('.formset-row, .subcomponent-row');
            const $button = $container.find('.delete-row');
            toggleDeleteState($container, $button, true);
        }
    });
}

// Handling clicks on any delete button
$(document).on('click', '.delete-row', function () {
        const $button = $(this);
        const $container = $button.closest('.formset-row, .subcomponent-row');
        toggleDeleteState($container, $button);
    }
);

// Skip step ---------------------------------------------------

function initSkipSubmitToggle() {
    const $formset = $("#form");
    const skipSubmit = $("#skip_submit");

    if ($formset.length && skipSubmit.length) {
        function hasAnyValue() {
            let hasValue = false;

            $formset.find("input, select, textarea").each(function () {
                const $field = $(this);
                const name = $field.attr("name");

                // Ignore hidden inputs and unmarked DELETE statements
                if ($field.attr("type") === "hidden") return;
                if (name && name.endsWith("-DELETE")) {
                    if ($field.is(":checked")) {
                        hasValue = true;
                        return false;
                    }
                    return;
                }

                const value = $field.val();
                if (value && value.trim() !== "") {
                    hasValue = true;
                    return false;
                }
            });

            return hasValue;
        }

        function toggleSkipSubmit() {
            if (hasAnyValue()) {
                $("#normal_submit").removeClass("d-none");
                skipSubmit.addClass("d-none");
            } else {
                $("#normal_submit").addClass("d-none");
                skipSubmit.removeClass("d-none");
            }
        }

        toggleSkipSubmit();

        $formset.on("input change", "input, select, textarea", toggleSkipSubmit);
    }
}

// Component formset ---------------------------------------------------

// Add subcomponent
$(document).on('click', '.add-subcomponent', function () {
    let componentIdx = $(this).attr('data-form-index');
    let $container = $(`.subcomponent-container[data-form-index="${componentIdx}"]`);
    let subIndex = $container.find('.subcomponent-row').length;

    // Clone the empty form template
    let $newRow = $('#empty-subform-template').html();

    // Replace __prefix__ with the current form index
    $newRow = $newRow.replace(/__subIndex__/g, subIndex).replace(/__componentIdx__/g, componentIdx);

    $container.append($newRow);

    // Update TOTAL_FORMS
    let $totalForms = $(`#id_subcomponent_form-${componentIdx}-TOTAL_FORMS`);
    $totalForms.val(parseInt($totalForms.val()) + 1);
});

// Remove subcomponent (new)
$(document).on('click', '.remove-subcomponent', function () {
    // Update TOTAL_FORMS
    let componentIdx = $(this).attr('data-form-index');
    let $totalForms = $(`#id_subcomponent_form-${componentIdx}-TOTAL_FORMS`);
    $totalForms.val(parseInt($totalForms.val()) - 1);

    $(this).closest('.subcomponent-row').remove();
});

// Final Step ---------------------------------------------

function submitFinalStep($this, url) {
    $.ajax({
        type: "post",
        url: url,
        cache: false,
        processData: false,
        contentType: false,
        success: function (response) {
            if (response.redirect_url) {
                window.location.href = response.redirect_url;
            } else {
                showPopupMessage(response.msg);
            }
        },
        error: function () {
            alert(error_server_message);
            $this.removeClass('disabled').removeAttr('disabled');
        }
    });
}