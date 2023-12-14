function switchStepImage(element, mainImgId, className, divThubId) {
  document.getElementById(mainImgId).src = element.src;
  var myElements = document.getElementsByClassName(className);
  for (var counter = 0; counter < myElements.length; counter++) {
    myElements[counter].classList.remove("active");
  }
  document.getElementById(divThubId).classList.add("active");
}

function switchCommentsVisibility(stepCommentsId) {
  elem = document.getElementById(stepCommentsId);
  if (elem.classList.contains("hide-comments")) {
    elem.classList.remove("hide-comments");
  } else {
    elem.classList.add("hide-comments");
  }
}
