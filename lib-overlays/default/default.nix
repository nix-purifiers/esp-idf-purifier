final: prev: {
  esp-idf-purifier = {
    readLock = import ./read-lock.nix { lib = final; };
  };
}
