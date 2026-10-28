/**
 * 콜로키움 드라이브 창구 (구글 Apps Script 웹앱)
 *
 * GitHub에서 돌아가는 수집 프로그램이 의장님 구글 드라이브의 파일을 읽고 쓰도록 이어 주는 창구입니다.
 * - 의장님 계정으로 실행되므로 구글 클라우드 설정이 필요 없습니다.
 * - 아래 ALLOWED 폴더 3개 밖은 읽지도 쓰지도 않습니다.
 * - 비밀 토큰이 맞는 요청만 받습니다. 토큰은 setup()을 한 번 실행하면 만들어지고,
 *   실행 로그에 한 번 보입니다. 그 값을 GitHub Secrets의 DRIVE_TOKEN에 넣습니다.
 *
 * 처음 한 번:
 *   1) 위쪽 함수 목록에서 setup 을 고르고 ▶실행 → 권한 허용 → 실행 로그의 토큰을 복사
 *   2) 배포 → 새 배포 → 유형: 웹 앱, 다음 사용자로 실행: 나, 액세스 권한: 모든 사용자 → 배포
 *   3) 나온 웹 앱 URL을 GitHub Secrets의 DRIVE_URL에 넣습니다.
 */

const ALLOWED = ['콜로키움', '콜로키움 수집데이터', '콜로키움 코딩 모음'];

function setup() {
  const props = PropertiesService.getScriptProperties();
  let token = props.getProperty('TOKEN');
  if (!token) {
    token = Utilities.getUuid().replace(/-/g, '') + Utilities.getUuid().replace(/-/g, '');
    props.setProperty('TOKEN', token);
  }
  DriveApp.getRootFolder();   // 드라이브 권한을 이때 묻게 한다
  Logger.log('DRIVE_TOKEN (GitHub Secrets에 넣을 값): ' + token);
}

function doPost(e) {
  try {
    const req = JSON.parse(e.postData.contents);
    const token = PropertiesService.getScriptProperties().getProperty('TOKEN');
    if (!token || req.token !== token) return out_({ ok: false, error: '토큰이 맞지 않음' });
    if (req.action === 'list') return out_({ ok: true, files: list_(req.path) });
    if (req.action === 'get') return out_(get_(req.path));
    if (req.action === 'put') return out_(put_(req.path, req.data, req.mime));
    return out_({ ok: false, error: '모르는 요청: ' + req.action });
  } catch (err) {
    return out_({ ok: false, error: String(err) });
  }
}

function out_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function nfc_(s) {
  return String(s).normalize('NFC');
}

// '콜로키움 수집데이터/20261028' 같은 경로 → 폴더. make가 true면 없는 폴더를 만든다.
function folder_(path, make) {
  const parts = nfc_(path).split('/').filter(String);
  if (!parts.length || ALLOWED.indexOf(parts[0]) < 0) throw new Error('허용되지 않은 폴더: ' + path);
  let f = DriveApp.getRootFolder();
  for (const p of parts) {
    let next = null;
    const it = f.getFolders();
    while (it.hasNext()) {
      const c = it.next();
      if (nfc_(c.getName()) === p) { next = c; break; }
    }
    if (!next) {
      if (!make) return null;
      next = f.createFolder(p);
    }
    f = next;
  }
  return f;
}

function split_(path) {
  const parts = nfc_(path).split('/');
  return [parts.slice(0, -1).join('/'), parts[parts.length - 1]];
}

function find_(folder, name) {
  const it = folder.getFiles();
  const hits = [];
  while (it.hasNext()) {
    const f = it.next();
    if (nfc_(f.getName()) === name) hits.push(f);
  }
  return hits;
}

function list_(path) {
  const f = folder_(path, false);
  if (!f) return [];
  const files = [];
  const it = f.getFiles();
  while (it.hasNext()) {
    const x = it.next();
    files.push({ name: nfc_(x.getName()), size: x.getSize(), modified: x.getLastUpdated().toISOString() });
  }
  return files;
}

function get_(path) {
  const [dir, name] = split_(path);
  const f = folder_(dir, false);
  const hits = f ? find_(f, name) : [];
  if (!hits.length) return { ok: true, found: false };
  hits.sort((a, b) => b.getLastUpdated() - a.getLastUpdated());
  return { ok: true, found: true, data: Utilities.base64Encode(hits[0].getBlob().getBytes()) };
}

// 같은 이름 파일은 휴지통으로 보내고 새로 만든다 (휴지통은 30일 뒤 자동으로 비워짐)
function put_(path, data, mime) {
  const [dir, name] = split_(path);
  const f = folder_(dir, true);
  find_(f, name).forEach(x => x.setTrashed(true));
  const blob = Utilities.newBlob(Utilities.base64Decode(data), mime || 'application/octet-stream', name);
  const made = f.createFile(blob);
  return { ok: true, id: made.getId() };
}
