import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { decrypt } from './lib/auth'

export async function middleware(request: NextRequest) {
  const isPublicRoute = request.nextUrl.pathname.startsWith('/api/') || 
                        request.nextUrl.pathname === '/login' ||
                        request.nextUrl.pathname === '/register';

  const sessionCookie = request.cookies.get("session")?.value;
  let isAuthenticated = false;

  if (sessionCookie) {
    try {
      const payload = await decrypt(sessionCookie);
      if (payload) isAuthenticated = true;
    } catch (err) {
      // Token is expired or invalid
    }
  }

  // If user is not authenticated and trying to access a private route (like the Diary app)
  if (!isAuthenticated && !isPublicRoute) {
    return NextResponse.redirect(new URL('/login', request.url))
  }

  // If user is authenticated and trying to access login/register, send them to app
  if (isAuthenticated && isPublicRoute && !request.nextUrl.pathname.startsWith('/api/')) {
    return NextResponse.redirect(new URL('/', request.url))
  }

  return NextResponse.next()
}

export const config = {
  // Matcher ignores next API, static files, images, etc.
  matcher: ['/((?!_next/static|_next/image|favicon.ico|.*\\.png$).*)'],
}
