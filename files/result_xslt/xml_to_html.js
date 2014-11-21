window.toggleResultData = function (event, task_id, bg_id) {
    switch_display = function(elem){
        if (elem.style.display == 'none'){
            elem.style.display = '';
        }else{
            elem.style.display = 'none';
        }
    }

    cell = event.target.parentNode;
    row = cell.parentNode;
    result_cell_i = cell.cellIndex + 2;
    result_cell = row.cells[result_cell_i];
    switch_display(result_cell);

    if (task_id !== undefined && bg_id !== undefined){
        rows = row.parentNode.rows;
        for (i = 0; i < rows.length; ++i){
            if (rows[i].name == ("task_id="+task_id+"bg_id="+bg_id)){
                switch_display(rows[i].cells[2]);
            }
        }
    }
}

window.highlightResultData = function (event, task_id, bg_id) {
    switch_background = function(elem){
        if (elem.style.background == ''){
            elem.style.background = 'lightblue';
        }else{
            elem.style.background = '';
        }
    }

    cell = event.target.parentNode;
    row = cell.parentNode;

    if (task_id !== undefined && bg_id !== undefined){
        rows = row.parentNode.rows;
        for (i = 0; i < rows.length; ++i){
            if (rows[i].getAttribute("name") == ("task_id="+task_id+"bg_id="+bg_id)){
                switch_background(rows[i]);
            }
        }
    }
}
