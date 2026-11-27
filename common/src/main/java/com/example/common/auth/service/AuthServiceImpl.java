package com.example.common.auth.service;

import com.example.common.auth.config.AuthProperties;
import com.example.common.auth.dto.AuthLoginRequest;
import com.example.common.auth.dto.AuthRegisterRequest;
import com.example.common.auth.exception.AuthException;
import com.example.common.auth.model.AuthUser;
import com.example.common.auth.model.AuthUserPrincipal;
import com.example.common.auth.repository.AuthUserRepository;
import org.springframework.http.HttpStatus;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import javax.servlet.http.HttpSession;
import java.util.Arrays;
import java.util.Locale;
import java.util.Optional;
import java.util.regex.Pattern;

/**
 * 登录态服务的默认实现。
 *
 * <p>负责三件事：入参规范化与规则校验、凭据比对、会话读写。用户名统一去掉首尾空格并转小写，
 * 因此注册与登录不区分大小写；密码要求长度为配置下限到 72、至少含一个英文字母与一个数字、
 * 不含任何空白字符，上限取 BCrypt 的有效输入长度，避免更长的部分被摘要算法静默丢弃。</p>
 *
 * <p>两处非显然的安全行为：一是登录失败一律返回同一句提示，不区分「用户不存在」与
 * 「密码错误」，防止通过错误信息枚举账号；二是注册或登录成功时先让旧会话失效再新建会话，
 * 用于防御会话固定攻击。</p>
 *
 * <p>用户读写全部经由 {@code AuthUserRepository}，本类不直接接触数据库。</p>
 */
public class AuthServiceImpl implements AuthService {

    /** 用户名规则：3 到 32 个字符，只能是英文字母、数字或下划线；校验前已转小写。 */
    private static final Pattern USERNAME_PATTERN = Pattern.compile("^[a-zA-Z0-9_]{3,32}$");

    /** 密码必须至少包含一个英文字母。 */
    private static final Pattern PASSWORD_LETTER_PATTERN = Pattern.compile(".*[A-Za-z].*");

    /** 密码必须至少包含一个数字。 */
    private static final Pattern PASSWORD_NUMBER_PATTERN = Pattern.compile(".*\\d.*");

    /** 密码不得包含空格、换行或制表符。 */
    private static final Pattern PASSWORD_SPACE_PATTERN = Pattern.compile(".*\\s.*");

    /** BCrypt 的有效输入上限，单位字符；超出部分不会参与摘要计算，因此在校验阶段直接拒绝。 */
    private static final int MAX_BCRYPT_PASSWORD_LENGTH = 72;

    private final AuthUserRepository authUserRepository;

    private final AuthPasswordService authPasswordService;

    private final AuthProperties authProperties;

    /**
     * 构造认证服务。
     *
     * @param authUserRepository 用户仓储，由业务模块实现
     * @param authPasswordService 密码摘要服务
     * @param authProperties 认证配置，提供 Session 属性名与密码长度下限
     */
    public AuthServiceImpl(AuthUserRepository authUserRepository,
                           AuthPasswordService authPasswordService,
                           AuthProperties authProperties) {
        this.authUserRepository = authUserRepository;
        this.authPasswordService = authPasswordService;
        this.authProperties = authProperties;
    }

    /**
     * 注册新用户并自动登录。
     *
     * <p>执行顺序：规范化用户名 → 校验用户名 → 校验密码 → 查重 → 生成摘要并入库 → 回读记录 → 写入会话。
     * 查重与入库之间存在并发窗口，最终唯一性仍依赖数据库的唯一约束。</p>
     *
     * @param authRequest 注册请求，用户名与密码为必填
     * @param request 当前请求，成功后写入新的 Session
     * @return 新建用户的会话主体
     * @throws AuthException 用户名不合规、密码不合规或用户名已存在时抛出 400；
     *     入库后回读不到记录时抛出 500
     */
    @Override
    public AuthUserPrincipal register(AuthRegisterRequest authRequest, HttpServletRequest request) {
        String username = normalizeUsername(authRequest.getUsername());
        validateUsername(username);
        validatePassword(authRequest.getPassword());
        if (authUserRepository.findByUsername(username).isPresent()) {
            throw new AuthException(HttpStatus.BAD_REQUEST,
                    "Username already exists",
                    "USERNAME_EXISTS",
                    Arrays.asList("该用户名已经被注册，请换一个用户名"));
        }
        String displayName = normalizeDisplayName(authRequest.getDisplayName(), username);
        Long id = authUserRepository.save(username, authPasswordService.hash(authRequest.getPassword()), displayName, "USER");
        AuthUser authUser = authUserRepository.findById(id)
                .orElseThrow(() -> new AuthException(HttpStatus.INTERNAL_SERVER_ERROR, "Failed to load created user"));
        AuthUserPrincipal principal = AuthUserPrincipal.from(authUser);
        savePrincipal(request, principal);
        return principal;
    }

    /**
     * 校验凭据并登录。
     *
     * <p>用户不存在、账号被禁用、密码不匹配三种情况返回同一提示，不泄露账号是否存在；
     * 密码比对交给 BCrypt，因此不在此处做长度或字符集校验。</p>
     *
     * @param authRequest 登录请求，密码为明文
     * @param request 当前请求，成功后写入新的 Session
     * @return 登录用户的会话主体
     * @throws AuthException 凭据无效或账号被禁用时抛出 401
     */
    @Override
    public AuthUserPrincipal login(AuthLoginRequest authRequest, HttpServletRequest request) {
        String username = normalizeUsername(authRequest.getUsername());
        AuthUser authUser = authUserRepository.findByUsername(username)
                .orElseThrow(() -> new AuthException(HttpStatus.UNAUTHORIZED, "Invalid username or password"));
        if (!authUser.isEnabled() || !authPasswordService.matches(authRequest.getPassword(), authUser.getPasswordHash())) {
            throw new AuthException(HttpStatus.UNAUTHORIZED, "Invalid username or password");
        }
        AuthUserPrincipal principal = AuthUserPrincipal.from(authUser);
        savePrincipal(request, principal);
        return principal;
    }

    /**
     * 注销当前会话。
     *
     * <p>会话不存在时直接返回，不抛异常，因此重复调用是安全的。</p>
     *
     * @param request 当前请求
     * @param response 当前响应，本实现未使用，保留以匹配服务契约
     */
    @Override
    public void logout(HttpServletRequest request, HttpServletResponse response) {
        HttpSession session = request.getSession(false);
        if (session != null) {
            session.invalidate();
        }
    }

    /**
     * 读取当前登录用户。
     *
     * <p>会话属性类型不符（例如旧版本写入过其他类型）时按未登录处理，
     * 而不是抛类型转换异常，避免升级后旧会话导致接口 500。</p>
     *
     * @param request 当前请求
     * @return 已登录时返回会话主体，否则返回空 Optional
     */
    @Override
    public Optional<AuthUserPrincipal> currentUser(HttpServletRequest request) {
        HttpSession session = request.getSession(false);
        if (session == null) {
            return Optional.empty();
        }
        Object user = session.getAttribute(authProperties.getSessionAttribute());
        if (user instanceof AuthUserPrincipal) {
            return Optional.of((AuthUserPrincipal) user);
        }
        return Optional.empty();
    }

    /**
     * 读取当前登录用户，未登录即失败。
     *
     * @param request 当前请求
     * @return 当前登录用户，保证非空
     * @throws AuthException 未登录时抛出 401，由拦截器或调用链统一响应
     */
    @Override
    public AuthUserPrincipal requireCurrentUser(HttpServletRequest request) {
        return currentUser(request).orElseThrow(() -> new AuthException(HttpStatus.UNAUTHORIZED, "Login required"));
    }

    /**
     * 写入登录主体。
     *
     * <p>先使旧会话失效再创建新会话，防止攻击者预先固定的会话 ID 在登录后继续有效；
     * 属性名取自 {@code love530.auth.session-attribute}。</p>
     *
     * @param request 当前请求
     * @param principal 待写入的登录主体
     */
    private void savePrincipal(HttpServletRequest request, AuthUserPrincipal principal) {
        HttpSession oldSession = request.getSession(false);
        if (oldSession != null) {
            oldSession.invalidate();
        }
        request.getSession(true).setAttribute(authProperties.getSessionAttribute(), principal);
    }

    /**
     * 规范化用户名：去首尾空格并转小写，null 归一为空串，交由后续规则校验拦截。
     *
     * @param username 原始输入，可为 {@code null}
     * @return 规范化后的用户名，永不为 {@code null}
     */
    private String normalizeUsername(String username) {
        return username == null ? "" : username.trim().toLowerCase(Locale.ROOT);
    }

    /**
     * 计算展示名：为空时回落到用户名，避免前端展示空白。
     *
     * @param displayName 原始展示名，可为 {@code null}
     * @param username 已规范化的用户名，作为兜底值
     * @return 去空格后的展示名
     */
    private String normalizeDisplayName(String displayName, String username) {
        if (displayName == null || displayName.trim().isEmpty()) {
            return username;
        }
        return displayName.trim();
    }

    /**
     * 校验用户名格式。
     *
     * @param username 已规范化的用户名
     * @throws AuthException 不符合规则时抛出 400，details 会列出全部规则供前端逐条提示
     */
    private void validateUsername(String username) {
        if (!USERNAME_PATTERN.matcher(username).matches()) {
            throw new AuthException(HttpStatus.BAD_REQUEST,
                    "Username does not meet the registration rules",
                    "USERNAME_INVALID",
                    Arrays.asList("用户名长度必须为 3-32 个字符", "用户名只能包含英文字母、数字或下划线", "用户名会自动去除首尾空格并转换为小写"));
        }
    }

    /**
     * 校验密码策略。
     *
     * <p>长度下限取自配置，上限固定 72 以贴合 BCrypt 的有效输入长度；
     * details 中的长度文案使用当前配置值，改配置后提示会同步变化。</p>
     *
     * @param password 明文密码，可为 {@code null}
     * @throws AuthException 不满足任一规则时抛出 400
     */
    private void validatePassword(String password) {
        if (password == null
                || password.length() < authProperties.getMinPasswordLength()
                || password.length() > MAX_BCRYPT_PASSWORD_LENGTH
                || !PASSWORD_LETTER_PATTERN.matcher(password).matches()
                || !PASSWORD_NUMBER_PATTERN.matcher(password).matches()
                || PASSWORD_SPACE_PATTERN.matcher(password).matches()) {
            throw new AuthException(HttpStatus.BAD_REQUEST,
                    "Password does not meet the registration rules",
                    "PASSWORD_INVALID",
                    Arrays.asList(
                            "密码长度必须为 " + authProperties.getMinPasswordLength() + "-72 个字符",
                            "密码至少包含 1 个英文字母",
                            "密码至少包含 1 个数字",
                            "密码不能包含空格、换行或制表符"
                    ));
        }
    }
}
