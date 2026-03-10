function showAnswer(){
    var nodes = document.getElementsByClassName('answer');
    for(var i = 0; i < nodes.length; i++){
        nodes[i].style.visibility = 'visible';
    }
}