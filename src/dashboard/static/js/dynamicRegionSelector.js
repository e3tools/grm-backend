let ancestors = [];
let governmentWorkerId = null;

function changeRegionTrigger(url, placeholder, government_worker_id = null) {
    governmentWorkerId = government_worker_id;
    $(document).on("change", ".region", function () {
        $("#id_administrative_region_value").val($("select.region:last").val());
        loadNextLevelRegions($(this), url, placeholder);
    });
}

function loadNextLevelRegions(current_level, url, placeholder) {
    let current_level_val = current_level.val();
    if (current_level_val !== '') {
        let select_region = $(".region");
        select_region.attr('disabled', true);
        let ajaxData = {
            parent_id: current_level_val,
        };
        // Add government_worker parameter if available
        if (governmentWorkerId !== null) {
            ajaxData.government_worker = governmentWorkerId;
        }
        $.ajax({
            type: 'GET',
            url: url,
            data: ajaxData,
            success: function (data) {
                if (data.length > 0) {
                    let id_select = 'id_' + data[0].administrative_level__name;
                    let label = data[0].administrative_level__name.replace(/^\w/, (c) => c.toUpperCase());
                    let child;
                    let new_input = document.createElement('div');
                    new_input.className = 'form-group row dynamic-select';

                    let label_element = document.createElement('label');
                    label_element.className = 'col-md-3 col-form-label';
                    label_element.setAttribute('for', id_select);
                    label_element.innerHTML = label;
                    new_input.appendChild(label_element);

                    let div_element = document.createElement('div');
                    div_element.className = 'col-md-9';

                    let select_element = document.createElement('select');
                    select_element.className = 'form-control region';
                    select_element.setAttribute("required", "");
                    select_element.setAttribute('id', id_select);
                    div_element.appendChild(select_element);

                    new_input.appendChild(div_element);

                    current_level.parent().parent().after(new_input);
                    child = current_level.closest('.form-group').next().find('.region');
                    child.select2({
                        allowClear: true,
                        placeholder: placeholder,
                        width: '100%',
                    });

                    let options = '<option value></option>';
                    $.each(data, function (index, value) {
                        let administrative_id = value.id;
                        let option = '<option value="' + administrative_id;
                        if (ancestors.includes(administrative_id)) {
                            option += '" selected="selected">';
                            ancestors = ancestors.filter(function (ancestor) {
                                return ancestor !== administrative_id;
                            });
                        } else {
                            option += '">';
                        }
                        option += value.name + '</option>';
                        options += option

                    });
                    child.html(options);
                    child.trigger('change');
                    let child_val = child.val();
                    if (child_val !== '') {
                        child.val(child_val)
                    }
                }
            },
            error: function (data) {
                alert(error_server_message + "Error " + data.status);
            }
        }).done(function () {
                if (ancestors.length <= 1) {
                    select_region.attr('disabled', false);
                    $('#next').prop('disabled', false);
                }
            }
        );
    } else {
        let next_selects = current_level.closest('.form-group').nextAll('.dynamic-select');
        $.each(next_selects, function (index, select) {
            select.remove();
        });
    }
}
