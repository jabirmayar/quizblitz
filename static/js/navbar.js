const NavbarComponent = {
    template: `
        <nav class="navbar-container">
            <!-- Desktop Navigation (md and up) -->
            <div class="hidden md:block">
                <div class="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
                    <!-- Left: Brand -->
                    <div class="flex items-center gap-6">
                        <a href="/" class="brand-title text-lg uppercase tracking-tighter hover:opacity-80 transition-opacity">
                            {{ config.APP_NAME }}
                        </a>
                        <div class="h-4 w-px bg-zinc-800"></div>
                        <span class="text-[10px] font-bold uppercase tracking-widest text-zinc-500">
                            {{ roleLabel }}
                        </span>
                    </div>

                    <!-- Center: Navigation Links -->
                    <div class="flex items-center gap-8">
                        <template v-if="role === 'admin'">
                            <a href="/admin/dashboard" :class="['nav-link', isActive('/admin/dashboard') ? 'active' : '']">Dashboard</a>
                            <a href="/admin/departments" :class="['nav-link', isActive('/admin/departments') ? 'active' : '']">Departments</a>
                            <a href="/admin/subjects" :class="['nav-link', isActive('/admin/subjects') ? 'active' : '']">Subjects</a>
                            <a href="/admin/teachers" :class="['nav-link', isActive('/admin/teachers') ? 'active' : '']">Teachers</a>
                            <a href="/admin/students" :class="['nav-link', isActive('/admin/students') ? 'active' : '']">Students</a>
                            <a href="/admin/results" :class="['nav-link', isActive('/admin/results') ? 'active' : '']">Results</a>
                        </template>
                        <template v-else-if="role === 'teacher'">
                            <a href="/teacher/dashboard" :class="['nav-link', isActive('/teacher/dashboard') ? 'active' : '']">Dashboard</a>
                            <a href="/teacher/quiz-create" :class="['nav-link', isActive('/teacher/quiz-create') ? 'active' : '']">Create Quiz</a>
                        </template>
                        <template v-else>
                            <a href="/dashboard" :class="['nav-link', isActive('/dashboard') ? 'active' : '']">My Quizzes</a>
                        </template>
                    </div>

                    <!-- Right: User Menu -->
                    <div class="flex items-center gap-4">
                        <a href="/reset-password" class="text-[10px] font-bold text-zinc-500 hover:text-white transition-colors uppercase tracking-widest">
                            Reset Password
                        </a>
                        <button @click="logout" class="text-[10px] font-bold text-zinc-500 hover:text-white transition-colors uppercase tracking-widest">
                            Sign Out
                        </button>
                    </div>
                </div>
            </div>

            <!-- Mobile Navigation (below md) -->
            <div class="block md:hidden">
                <div class="px-6 h-14 flex items-center justify-between">
                    <!-- Left: Brand -->
                    <a href="/" class="brand-title text-base uppercase tracking-tighter">
                        {{ config.APP_NAME }}
                    </a>

                    <!-- Right: Hamburger Menu -->
                    <button @click="toggleMobileMenu" class="text-white focus:outline-none">
                        <svg v-if="!mobileMenuOpen" class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path>
                        </svg>
                        <svg v-else class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>

                <!-- Mobile Menu Dropdown -->
                <div v-if="mobileMenuOpen" class="mobile-menu-dropdown">
                    <div class="py-4 px-6 space-y-3 border-t border-zinc-800">
                        <!-- Role Label -->
                        <p class="text-[10px] font-bold uppercase tracking-widest text-zinc-500 mb-4">
                            {{ roleLabel }}
                        </p>

                        <!-- Navigation Links -->
                        <template v-if="role === 'admin'">
                            <a href="/admin/dashboard" @click="toggleMobileMenu" :class="['mobile-nav-link', isActive('/admin/dashboard') ? 'active' : '']">Dashboard</a>
                            <a href="/admin/departments" @click="toggleMobileMenu" :class="['mobile-nav-link', isActive('/admin/departments') ? 'active' : '']">Departments</a>
                            <a href="/admin/subjects" @click="toggleMobileMenu" :class="['mobile-nav-link', isActive('/admin/subjects') ? 'active' : '']">Subjects</a>
                            <a href="/admin/teachers" @click="toggleMobileMenu" :class="['mobile-nav-link', isActive('/admin/teachers') ? 'active' : '']">Teachers</a>
                            <a href="/admin/students" @click="toggleMobileMenu" :class="['mobile-nav-link', isActive('/admin/students') ? 'active' : '']">Students</a>
                            <a href="/admin/results" @click="toggleMobileMenu" :class="['mobile-nav-link', isActive('/admin/results') ? 'active' : '']">Results</a>
                        </template>
                        <template v-else-if="role === 'teacher'">
                            <a href="/teacher/dashboard" @click="toggleMobileMenu" :class="['mobile-nav-link', isActive('/teacher/dashboard') ? 'active' : '']">Dashboard</a>
                            <a href="/teacher/quiz-create" @click="toggleMobileMenu" :class="['mobile-nav-link', isActive('/teacher/quiz-create') ? 'active' : '']">Create Quiz</a>
                        </template>
                        <template v-else>
                            <a href="/dashboard" @click="toggleMobileMenu" :class="['mobile-nav-link', isActive('/dashboard') ? 'active' : '']">My Quizzes</a>
                        </template>

                        <!-- User Info & Logout -->
                        <div class="border-t border-zinc-800 pt-3 mt-3">
                            <a href="/reset-password" @click="toggleMobileMenu" class="mobile-nav-link">
                                Reset Password
                            </a>
                            <button @click="logout" class="mobile-nav-link text-red-400 hover:text-red-300">
                                Sign Out
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </nav>
    `,
    setup() {
        const mobileMenuOpen = Vue.ref(false);
        const currentPath = Vue.ref(window.location.pathname || '/');
        const getJwtPayload = (token) => {
            try {
                if (!token) return null;
                const parts = token.split('.');
                if (parts.length !== 3) return null;
                const base64Url = parts[1];
                const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
                const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
                return JSON.parse(atob(padded));
            } catch (_) {
                return null;
            }
        };

        const token = localStorage.getItem('token');
        const payload = getJwtPayload(token);
        const role = Vue.ref((payload && payload.role) ? payload.role : 'student');

        const config = Vue.computed(() => window.CONFIG || { APP_NAME: 'QuizBlitz' });

        const roleLabel = Vue.computed(() => {
            const labels = {
                admin: 'Administrator',
                teacher: 'Instructor',
                student: 'Student Portal'
            };
            return labels[role.value] || 'User';
        });

        const toggleMobileMenu = () => {
            mobileMenuOpen.value = !mobileMenuOpen.value;
        };

        const isActive = (href) => {
            const path = currentPath.value || '/';

            if (href === '/dashboard') {
                return path === '/dashboard' || path.startsWith('/quiz') || path.startsWith('/result') || path.startsWith('/review');
            }

            if (href === '/teacher/dashboard') {
                return path === '/teacher/dashboard'
                    || path.startsWith('/teacher/questions')
                    || path.startsWith('/teacher/quiz-edit')
                    || path.startsWith('/teacher/results')
                    || path.startsWith('/teacher/grade');
            }

            return path === href || path.startsWith(href + '/');
        };

        const logout = () => {
            localStorage.removeItem('token');
            localStorage.removeItem('displayName');
            window.location.href = '/';
        };

        return {
            mobileMenuOpen,
            role,
            config,
            roleLabel,
            toggleMobileMenu,
            isActive,
            logout
        };
    }
};

// Export the component for use in individual pages
window.NavbarComponent = NavbarComponent;
