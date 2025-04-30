function clean(string){
  let lettersOnly = string.replace(/[^a-zA-Z]/g, "");
  let caps = lettersOnly.toUpperCase();
  return caps;
}

//console.log(clean('lkm,..only655.?'));

function patristocratCipher(string,key,shift){
  let sample = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
  let keyNd =  [...new Set(key)].join("");
  let deletion = sample
    .split("")
    .filter(letter => !keyNd.includes(letter))
    .join("");

  let cipher =  deletion.slice(25 - shift, 25) + keyNd + deletion.slice(0, 25-shift); 

  let vals = string.split("")
  let result = [];
  for (let i = 0; i < vals.length; i++){
    let value = vals[i].charCodeAt(0) - 64;
    result.push(cipher[value]);
  } 
  return result.join("");

} 

console.log(patristocratCipher(clean("catalan"),clean("carnivorous"),15));