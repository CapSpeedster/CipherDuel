function clean(string){
  let lettersOnly = string.replace(/[^a-zA-Z]/g, "");
  let caps = lettersOnly.toUpperCase();
}

console.log(clean('lkm,..only655.?'));