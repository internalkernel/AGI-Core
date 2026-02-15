import { Navigate, Outlet } from 'react-router-dom';
import { getStoredToken } from '../../hooks/useAuth';

export default function AuthGuard({ children }: { children?: React.ReactNode }) {
  const token = getStoredToken();

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return children ? <>{children}</> : <Outlet />;
}
