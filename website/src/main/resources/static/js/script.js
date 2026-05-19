console.log('%cCopyright © 2024-2025 Caleb XXY', 'background-color: #a285e6; color: white; font-size: 24px; font-weight: bold; padding: 10px;');
console.log('%c   /\\_/\\', 'color: #f7b267; font-size: 20px;');
console.log('%c  ( o.o )', 'color: #f7b267; font-size: 20px;');
console.log(' %c  > ^ <', 'color: #f7b267; font-size: 20px;');
console.log('  %c /  ~ \\', 'color: #f7b267; font-size: 20px;');
console.log('  %c/______\\', 'color: #f7b267; font-size: 20px;');




document.addEventListener('contextmenu', function(event) {
  event.preventDefault(); // 阻止默认的上下文菜单行为
});


function openTab(tabName) {
    // Hide all tab content
    var tabContents = document.getElementsByClassName('tab-content');
    for (var i = 0; i < tabContents.length; i++) {
        tabContents[i].classList.remove('content-active');
    }
    
    // Remove active class from all buttons
    var tabButtons = document.getElementsByClassName('tab-button');
    for (var i = 0; i < tabButtons.length; i++) {
        tabButtons[i].classList.remove('but-active');
    }
    
    // Show the selected tab content
    document.getElementById(tabName).classList.add('content-active');
    
    // Add active class to the clicked button
    event.target.classList.add('but-active');
}


function toggleClass(selector, className) {
    var elements = document.querySelectorAll(selector);
    elements.forEach(function (element) {
        element.classList.toggle(className);
    });
}

function PopUp(imageURL) {
    var popupMainElement = document.querySelector(".pop-up-img");
    if (imageURL) {
        popupMainElement.src = imageURL;
    }
    toggleClass(".pop-up-main", "active");
    toggleClass(".pop-up", "active");
    toggleClass(".pop-up-close", "active");
}

function playSound(soundUrl) {
  const audio = new Audio(soundUrl);
  audio.play().catch(e => console.error("Failed to play sound effect:", e));
}

function left() {
    toggleClass(".left-main", "left-main-open");
    toggleClass(".left", "left-open");

}


document.addEventListener('DOMContentLoaded', function () {


    var themeState = getCookie("themeState") || "Light";
    const htmlTag = document.querySelector('html');
    var svgItems = document.getElementsByTagName("svg");
    var tanChiShe = document.getElementById("tanChiShe");




    function changeSvg(color) {
        for (var i = 0; i < svgItems.length; i++) {
            var paths = svgItems[i].getElementsByTagName("path");
            for (var j = 0; j < paths.length; j++) {
                paths[j].setAttribute("fill", color);
            }
        }
    }



    function changeTheme(theme) {
        if (theme == "Dark") {
            themeState = "Dark";
            changeSvg("#ffffff");
            tanChiShe.src = "/svg/snake-Dark.svg";
            htmlTag.dataset.theme = 'dark';
        } else if (theme == "Light") {
            themeState = "Light";
            changeSvg("#000000");
            tanChiShe.src = "./svg/snake-Light.svg";
            htmlTag.dataset.theme = '';
        }
        setCookie("themeState", theme, 365);
    }




    function setCookie(name, value, days) {
        var expires = "";
        if (days) {
            var date = new Date();
            date.setTime(date.getTime() + days * 24 * 60 * 60 * 1000);
            expires = "; expires=" + date.toUTCString();
        }
        document.cookie = name + "=" + value + expires + "; path=/";
    }


    function getCookie(name) {
        var nameEQ = name + "=";
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = cookies[i];
            while (cookie.charAt(0) == ' ') {
                cookie = cookie.substring(1, cookie.length);
            }
            if (cookie.indexOf(nameEQ) == 0) {
                return cookie.substring(nameEQ.length, cookie.length);
            }
        }
        return null;
    }


    document.querySelectorAll('.tab-button').forEach(button => {
    button.addEventListener('click', () => {
            playSound('./soundeffects/click.mp3');
        });
    });

    const switchCheckbox = document.getElementById('myonoffswitch');
    /*夜间自动打开暗色主题*/
    const currentTime = new Date();
    const currentHour = currentTime.getHours();
    if (currentHour >= 20 || currentHour < 6) {
        switchCheckbox.checked = false;
        changeTheme('Dark');
    }


    switchCheckbox.addEventListener('change', function () {

        if (themeState == "Dark") {

            playSound('./soundeffects/light-on.mp3')
            changeTheme("Light");

        } else if (themeState == "Light") {

            playSound('./soundeffects/light-off.mp3')
            changeTheme("Dark");
        }
    });

    if (themeState == "Dark") {
        switchCheckbox.checked = false;
    }
    changeTheme(themeState);




    /*加载效果*/
    // var pageLoading = document.querySelector("#PageLoading");
    // var center = document.getElementById("PageLoading-zyyo-center");
    // setTimeout(function () {
    //     pageLoading.style.opacity = '0';
    //     center.style.height = "500px";
    //     center.style.width = "500px";
    //     center.style.opacity = "0";
    //     pageLoading.style.backgroundSize = "200%";
    // }, 300);

    // 暂时强制深色模式
    // changeTheme("Dark")

    /*淡入效果*/
    var projectItems = document.querySelectorAll(".projectItem");
    function checkProjectItems() {
        for (var i = 0; i < projectItems.length; i++) {
            var projectItem = projectItems[i];
            var projectItemTop = projectItem.getBoundingClientRect().top;

            if (projectItemTop < window.innerHeight * 1.2) {
                // projectItem.classList.add("fade-in-visible");
            }
        }
    }

    window.addEventListener("scroll", checkProjectItems);
    window.addEventListener("resize", checkProjectItems);

});

// FAQ Toggle Function
function toggleFAQ(element) {
    const faqItem = element.parentElement;
    const isActive = faqItem.classList.contains('active');

    playSound('./soundeffects/collapsible_open.mp3')
    
    // Close all other FAQ items
    // const allFaqItems = document.querySelectorAll('.faq-item');
    // allFaqItems.forEach(item => {
    //     item.classList.remove('active');
    // });

    // Collapse current FAQ item
    if (isActive) {
        faqItem.classList.remove('active');
    }
    
    // Toggle current FAQ item
    if (!isActive) {
        faqItem.classList.add('active');
    }
}

document.addEventListener('DOMContentLoaded', function () {
    var authPopup = document.querySelector('.auth-pop-up');
    var authForm = document.querySelector('.auth-pop-up-main');
    var authTitle = document.querySelector('.auth-pop-up-title');
    var authCopy = document.querySelector('.auth-pop-up-copy');
    var authUsername = document.querySelector('.auth-username');
    var authDisplayName = document.querySelector('.auth-display-name');
    var authPassword = document.querySelector('.auth-password');
    var authMessage = document.querySelector('.auth-message');
    var authSubmitButton = document.querySelector('.auth-submit-button');
    var loginButton = document.querySelector('.auth-login-button');
    var registerButton = document.querySelector('.auth-register-button');
    var logoutButton = document.querySelector('.auth-logout-button');
    var closeButton = document.querySelector('.auth-pop-up-close');
    var guardedProjectLinks = document.querySelectorAll('.projectItem[data-auth-required="true"]');
    var authMode = 'login';
    var currentUser = null;
    var pendingProtectedLink = null;

    if (!authPopup || !authForm) {
        return;
    }

    function setAuthState(user) {
        var loggedIn = !!user;
        currentUser = user || null;
        if (loginButton) {
            loginButton.style.display = loggedIn ? 'none' : 'flex';
        }
        if (registerButton) {
            registerButton.style.display = loggedIn ? 'none' : 'flex';
        }
        if (logoutButton) {
            logoutButton.style.display = loggedIn ? 'flex' : 'none';
        }
    }

    function openAuth(mode) {
        authMode = mode;
        authTitle.textContent = mode === 'register' ? 'Register' : 'Login';
        if (authCopy) {
            authCopy.textContent = mode === 'register'
                ? 'Create your account to keep protected projects available across this workspace.'
                : 'Sign in to unlock protected projects and keep your workspace connected.';
        }
        if (authSubmitButton) {
            authSubmitButton.textContent = mode === 'register' ? 'Create account' : 'Continue';
        }
        authDisplayName.style.display = mode === 'register' ? 'block' : 'none';
        authPassword.setAttribute('autocomplete', mode === 'register' ? 'new-password' : 'current-password');
        authMessage.textContent = '';
        authForm.reset();
        authPopup.classList.add('active');
    }

    function openProtectedLink(link) {
        if (!link || !link.href) {
            return;
        }
        window.open(link.href, link.target || '_blank', 'noopener');
    }

    function requireLoginForLink(event, link) {
        event.preventDefault();
        if (currentUser) {
            openProtectedLink(link);
            return;
        }
        fetch('/api/auth/me')
            .then(function (response) {
                if (!response.ok) {
                    return null;
                }
                return response.json();
            })
            .then(function (payload) {
                if (payload && payload.user) {
                    setAuthState(payload.user);
                    openProtectedLink(link);
                    return;
                }
                pendingProtectedLink = {
                    href: link.href,
                    target: link.target
                };
                openAuth('login');
                authMessage.textContent = 'Login required for ' + (link.getAttribute('data-auth-target-name') || 'this project');
            })
            .catch(function () {
                pendingProtectedLink = {
                    href: link.href,
                    target: link.target
                };
                openAuth('login');
                authMessage.textContent = 'Login required';
            });
    }

    function closeAuth() {
        authPopup.classList.remove('active');
    }

    function loadMe() {
        fetch('/api/auth/me')
            .then(function (response) {
                if (!response.ok) {
                    setAuthState(null);
                    return null;
                }
                return response.json();
            })
            .then(function (payload) {
                if (payload) {
                    setAuthState(payload.user);
                }
            })
            .catch(function () {
                setAuthState(null);
            });
    }

    if (loginButton) {
        loginButton.addEventListener('click', function () {
            openAuth('login');
        });
    }
    if (registerButton) {
        registerButton.addEventListener('click', function () {
            openAuth('register');
        });
    }
    if (closeButton) {
        closeButton.addEventListener('click', closeAuth);
    }
    if (logoutButton) {
        logoutButton.addEventListener('click', function () {
            fetch('/api/auth/logout', { method: 'POST' }).then(function () {
                setAuthState(null);
            });
        });
    }
    guardedProjectLinks.forEach(function (link) {
        link.addEventListener('click', function (event) {
            requireLoginForLink(event, link);
        });
    });

    authForm.addEventListener('submit', function (event) {
        event.preventDefault();
        authMessage.textContent = '';
        var payload = {
            username: authUsername.value,
            password: authPassword.value
        };
        if (authMode === 'register') {
            payload.displayName = authDisplayName.value;
        }
        fetch(authMode === 'register' ? '/api/auth/register' : '/api/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        }).then(function (response) {
            if (!response.ok) {
                throw new Error('auth failed');
            }
            return response.json();
        }).then(function (payload) {
            setAuthState(payload.user);
            closeAuth();
            if (pendingProtectedLink) {
                openProtectedLink(pendingProtectedLink);
                pendingProtectedLink = null;
            }
        }).catch(function () {
            authMessage.textContent = 'Login or register failed';
        });
    });

    loadMe();
});
