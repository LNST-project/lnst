window.toggleResultData = function (event, task_id, bg_id) {
    switch_display = function(elem){
        if (elem.style.display == 'none')
            elem.style.display = '';
        else
            elem.style.display = 'none';
    }

    row = event.target.parentNode;
    result_row_i = row.rowIndex + 1;
    result_row = row.parentNode.rows[result_row_i];
    switch_display(result_row);

    if (task_id !== undefined && bg_id !== undefined){
        rows = row.parentNode.childNodes;
        for (i = 0; i < rows.length; ++i){
            if (rows[i].id == ("task_id="+task_id+"bg_id="+bg_id))
                rows[i].style.display = result_row.style.display;
        }
    }
}
