function refresh() {
    var url = location.origin;
    var pathname = location.pathname;
    var hash = location.hash;

location = url + pathname + '?application_refresh=' + (Math.random() * 100000) + hash;
}