// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title IncidentLogger
 * @notice Tamper-proof forensic ledger for cyber incidents.
 * Deployed on local Ganache chain — NO cloud provider.
 */
contract IncidentLogger {

    // ─── Data Types ───────────────────────────────────────────────
    struct Incident {
        uint256  id;
        bytes32  incidentHash;   // keccak256 proof — immutable fingerprint
        uint256  timestamp;      // block.timestamp — cannot be faked
        string   sourceIP;       // attacker IP address
        string   attackLabel;    // human-readable attack name
        uint8    severity;       // 1 (low) to 10 (critical)
        bool     isBlocked;      // was the node isolated?
        string   forensicsURI;   // pointer to SQLite: "local://incident/42"
    }

    // ─── State Variables ──────────────────────────────────────────
    mapping(uint256 => Incident) private _incidents;
    mapping(string  => bool)     public  blockedIPs;
    mapping(string  => uint256[]) private _ipIncidentHistory;

    uint256 public incidentCount;
    address public immutable deployer;

    // ─── Events ───────────────────────────────────────────────────
    event IncidentLogged(uint256 indexed id, bytes32 indexed incidentHash, string sourceIP, string attackLabel, uint256 timestamp);
    event NodeIsolated(string indexed sourceIP, uint256 incidentId, uint256 timestamp);
    event NodeReleased(string indexed sourceIP, uint256 timestamp, string reason);

    // ─── Constructor ──────────────────────────────────────────────
    constructor() {
        deployer = msg.sender;
        incidentCount = 0;
    }

    // ─── Core Function: Log an incident ───────────────────────────
    function logIncident(
        string  memory _sourceIP,
        string  memory _attackLabel,
        uint8          _severity,
        bool           _isBlocked,
        string  memory _forensicsURI
    ) external returns (uint256 newId) {
        require(bytes(_sourceIP).length > 0,    "IP cannot be empty");
        require(bytes(_attackLabel).length > 0, "Attack label required");
        require(_severity >= 1 && _severity <= 10, "Severity: 1-10 only");

        unchecked { newId = ++incidentCount; }

        // Generate tamper-proof fingerprint
        bytes32 hash = keccak256(abi.encodePacked(
            _sourceIP,
            block.timestamp,
            _attackLabel,
            _severity,
            newId
        ));

        _incidents[newId] = Incident({
            id:            newId,
            incidentHash:  hash,
            timestamp:     block.timestamp,
            sourceIP:      _sourceIP,
            attackLabel:   _attackLabel,
            severity:      _severity,
            isBlocked:     _isBlocked,
            forensicsURI:  _forensicsURI
        });

        _ipIncidentHistory[_sourceIP].push(newId);

        if (_isBlocked) {
            blockedIPs[_sourceIP] = true;
            emit NodeIsolated(_sourceIP, newId, block.timestamp);
        }

        emit IncidentLogged(newId, hash, _sourceIP, _attackLabel, block.timestamp);
        return newId;
    }

    // ─── Read Functions ───────────────────────────────────────────
    function getIncident(uint256 _id) external view returns (Incident memory) {
        require(_id > 0 && _id <= incidentCount, "Incident not found");
        return _incidents[_id];
    }

    function getIncidentCount() external view returns (uint256) {
        return incidentCount;
    }

    function isIPBlocked(string memory _ip) external view returns (bool) {
        return blockedIPs[_ip];
    }

    function getIPHistory(string memory _ip) external view returns (uint256[] memory) {
        return _ipIncidentHistory[_ip];
    }

    // ─── Verify tamper-proof integrity ────────────────────────────
    function verifyIncident(
        uint256 _id,
        string  memory _sourceIP,
        string  memory _attackLabel,
        uint8          _severity,
        uint256        _timestamp
    ) external view returns (bool) {
        Incident storage inc = _incidents[_id];
        bytes32 recomputed = keccak256(abi.encodePacked(
            _sourceIP, _timestamp, _attackLabel, _severity, _id
        ));
        return recomputed == inc.incidentHash;
    }

    // ─── Admin: Release a blocked node ───────────────────────────
    function releaseNode(string memory _ip, string memory _reason) external {
        require(blockedIPs[_ip], "IP is not blocked");
        blockedIPs[_ip] = false;
        emit NodeReleased(_ip, block.timestamp, _reason);
    }
}

