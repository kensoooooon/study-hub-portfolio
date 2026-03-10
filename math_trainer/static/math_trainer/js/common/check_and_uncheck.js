function checkAllStatus(target){
    let statuses = document.getElementsByName(target);

    for (let i =0; i < statuses.length; i++){
        if (!(statuses[i].checked)){
            statuses[i].checked = true;
        }
    }
}

function uncheckAllStatus(target){
    let statuses = document.getElementsByName(target);

    for (let i =0; i < statuses.length; i++){
        if (statuses[i].checked){
            statuses[i].checked = false;
        }
    }
}