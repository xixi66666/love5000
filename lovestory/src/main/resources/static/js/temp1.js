            const isLoggedIn = sessionStorage.getItem('isLoggedIn');
            if (!isLoggedIn || isLoggedIn !== 'true') {
                window.location.href = '/login.html';
            }
        })();
