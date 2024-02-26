let ancestors = [];

function changeRegionTrigger(url, placeholder) {
  $(document).on('change', '.region', function () {
    $('#id_administrative_region_value').val($('select.region:last').val());
    loadNextLevelRegions($(this), url, placeholder);
  });
}

function loadNextLevelRegions(current_level, url, placeholder) {
  let current_level_val = current_level.val();
  console.log({ url });
  console.log(
    'current_level_val para cargar proximo selector: ' + current_level_val
  );
  if (current_level_val !== '') {
    let select_region = $('.region');
    select_region.attr('disabled', true);
    $.ajax({
      type: 'GET',
      url: url,
      data: {
        parent_id: current_level_val,
      },
      success: function (data) {
        console.log(data);
        if (data.length > 0) {
          let id_select = 'id_' + data[0].administrative_level;
          let label = data[0].administrative_level.replace(/^\w/, (c) =>
            c.toUpperCase()
          );
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
          select_element.setAttribute('required', '');
          select_element.setAttribute('id', id_select);
          div_element.appendChild(select_element);

          new_input.appendChild(div_element);

          current_level.parent().parent().after(new_input);
          child = current_level.closest('.form-group').next().find('.region');
          child.select2({
            allowClear: true,
            placeholder: placeholder,
          });
          $(child).next().find('b[role="presentation"]').hide();
          $(child)
            .next()
            .find('.select2-selection__arrow')
            .append(
              '<i class="fas fa-chevron-circle-down text-primary" style="margin-top:12px;"></i>'
            );

          let options = '<option value></option>';

          // Prevent user from selecting regions they don't belong by prefilling their region and the only selectable option
          let found = false;
          $.each(data, function (index, value) {
            // Check if the administrative_id exists in the ancestors array
            if (ancestors.includes(value.administrative_id)) {
              // If it exists, create and append the option
              options +=
                '<option value="' +
                value.administrative_id +
                '" selected>' +
                value.name +
                '</option>';
              found = true;

              ancestors = ancestors.filter(function (ancestor) {
                return ancestor !== value.administrative_id;
              });
              return false;
            }
          });

          // If the region doesn;t exist in ancestor, create options for all other values
          if (!found) {
            $.each(data, function (index, value) {
              options +=
                '<option value="' +
                value.administrative_id +
                '">' +
                value.name +
                '</option>';
            });
          }

          child.html(options);
          child.trigger('change');
          let child_val = child.val();
          if (child_val !== '') {
            child.val(child_val);
          }
        }
      },
      error: function (data) {
        alert(error_server_message + 'Error ' + data.status);
      },
    }).done(function () {
      console.log('*********', ancestors);
      if (ancestors.length <= 1) {
        select_region.attr('disabled', false);
        $('#next').prop('disabled', false);
      }
    });
  } else {
    let next_selects = current_level
      .closest('.form-group')
      .nextAll('.dynamic-select');
    $.each(next_selects, function (index, select) {
      select.remove();
    });
  }
}

function loadRegionSelectors(url) {
  let administrative_region_value = $('#id_administrative_region_value').val();
  $.ajax({
    type: 'GET',
    url: url,
    data: {
      administrative_id: administrative_region_value,
    },
    success: function (data) {
      if (data.length > 0) {
        data = data.slice(1);
        data.push(administrative_region_value);
        ancestors = data;
        loadNextLevelRegions(
          $('select.region:last'),
          get_choices_url,
          choice_placeholder
        );
      } else {
        $('#next').prop('disabled', false);
      }
    },
    error: function (data) {
      alert(error_server_message + 'Error ' + data.status);
    },
  });
}
