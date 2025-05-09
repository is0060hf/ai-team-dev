import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Heading,
  Text,
  Flex,
  Spinner,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Badge,
  useColorModeValue,
  Input,
  Select,
  Button,
  IconButton,
  Tooltip,
  VStack,
  HStack,
  Collapse,
  Divider,
  Code,
  Alert,
  AlertIcon,
  useToast
} from '@chakra-ui/react';
import { 
  SearchIcon, 
  TimeIcon, 
  ChevronDownIcon, 
  ChevronRightIcon, 
  InfoIcon,
  RepeatIcon,
  DownloadIcon
} from '@chakra-ui/icons';
import axios from 'axios';

// トレースデータをフェッチするAPI URL
const API_URL = '/api/traces';

const TraceViewer = () => {
  const [traces, setTraces] = useState([]);
  const [filteredTraces, setFilteredTraces] = useState([]);
  const [selectedTrace, setSelectedTrace] = useState(null);
  const [expandedSpans, setExpandedSpans] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [timeRange, setTimeRange] = useState('1h'); // 1時間
  const [serviceFilter, setServiceFilter] = useState('');
  const [services, setServices] = useState([]);
  const [statusFilter, setStatusFilter] = useState('all');
  const [sortBy, setSortBy] = useState('timestamp');
  const [sortDirection, setSortDirection] = useState('desc');
  
  const toast = useToast();
  const timeoutRef = useRef(null);
  const tableRef = useRef(null);
  
  // 色設定
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const hoverBgColor = useColorModeValue('gray.50', 'gray.700');
  const selectedBgColor = useColorModeValue('blue.50', 'blue.900');
  const textColor = useColorModeValue('gray.800', 'white');
  const mutedColor = useColorModeValue('gray.600', 'gray.400');
  
  // トレースデータのフェッチ
  const fetchTraces = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await axios.get(API_URL, {
        params: {
          timeRange,
          service: serviceFilter || undefined,
          status: statusFilter !== 'all' ? statusFilter : undefined
        }
      });
      
      const tracesData = response.data.traces || [];
      setTraces(tracesData);
      
      // サービス一覧を抽出
      const uniqueServices = [...new Set(tracesData.flatMap(trace => 
        trace.spans.map(span => span.service)
      ))].filter(Boolean).sort();
      
      setServices(uniqueServices);
      
      // 検索クエリを適用
      filterTraces(tracesData, searchQuery);
      
    } catch (err) {
      console.error('トレースデータの取得に失敗しました:', err);
      setError('トレースデータの取得に失敗しました。');
      toast({
        title: 'エラー',
        description: 'トレースデータの取得に失敗しました。',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setLoading(false);
    }
  };
  
  // 初回読み込み時とフィルター変更時にデータをフェッチ
  useEffect(() => {
    fetchTraces();
    
    // 自動更新（30秒ごと）
    const intervalId = setInterval(fetchTraces, 30000);
    
    return () => {
      clearInterval(intervalId);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [timeRange, serviceFilter, statusFilter]);
  
  // 検索クエリの適用
  const filterTraces = (tracesData, query) => {
    if (!query) {
      setFilteredTraces(sortTraces(tracesData));
      return;
    }
    
    const lowerQuery = query.toLowerCase();
    const filtered = tracesData.filter(trace => 
      trace.trace_id.toLowerCase().includes(lowerQuery) ||
      trace.name.toLowerCase().includes(lowerQuery) ||
      trace.spans.some(span => 
        span.name.toLowerCase().includes(lowerQuery) ||
        (span.service && span.service.toLowerCase().includes(lowerQuery)) ||
        (span.attributes && Object.entries(span.attributes).some(([key, value]) => 
          key.toLowerCase().includes(lowerQuery) || 
          String(value).toLowerCase().includes(lowerQuery)
        ))
      )
    );
    
    setFilteredTraces(sortTraces(filtered));
  };
  
  // 検索クエリの変更時に遅延適用（タイピング中のパフォーマンス向上）
  useEffect(() => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    
    timeoutRef.current = setTimeout(() => {
      filterTraces(traces, searchQuery);
    }, 300);
    
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [searchQuery, traces]);
  
  // トレースの並べ替え
  const sortTraces = (tracesToSort) => {
    return [...tracesToSort].sort((a, b) => {
      let valueA, valueB;
      
      switch (sortBy) {
        case 'timestamp':
          valueA = new Date(a.start_time).getTime();
          valueB = new Date(b.start_time).getTime();
          break;
        case 'duration':
          valueA = a.duration_ms;
          valueB = b.duration_ms;
          break;
        case 'name':
          valueA = a.name;
          valueB = b.name;
          break;
        case 'spanCount':
          valueA = a.spans.length;
          valueB = b.spans.length;
          break;
        default:
          valueA = new Date(a.start_time).getTime();
          valueB = new Date(b.start_time).getTime();
      }
      
      // 文字列の場合は大文字小文字を区別しない
      if (typeof valueA === 'string' && typeof valueB === 'string') {
        valueA = valueA.toLowerCase();
        valueB = valueB.toLowerCase();
      }
      
      return sortDirection === 'asc' 
        ? (valueA > valueB ? 1 : -1)
        : (valueA < valueB ? 1 : -1);
    });
  };
  
  // 並べ替え条件の変更
  useEffect(() => {
    setFilteredTraces(sortTraces(filteredTraces));
  }, [sortBy, sortDirection]);
  
  // 並べ替え条件の切り替え
  const toggleSort = (column) => {
    if (sortBy === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(column);
      setSortDirection('asc');
    }
  };
  
  // スパンの展開/折りたたみの切り替え
  const toggleSpan = (spanId) => {
    setExpandedSpans(prev => ({
      ...prev,
      [spanId]: !prev[spanId]
    }));
  };
  
  // トレースの選択
  const handleSelectTrace = (trace) => {
    setSelectedTrace(trace);
    setExpandedSpans({}); // 選択時に展開状態をリセット
  };
  
  // トレースをJSONとしてエクスポート
  const exportTraceJson = () => {
    if (!selectedTrace) return;
    
    const dataStr = JSON.stringify(selectedTrace, null, 2);
    const dataUri = `data:application/json;charset=utf-8,${encodeURIComponent(dataStr)}`;
    
    const exportFileDefaultName = `trace-${selectedTrace.trace_id}.json`;
    
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
    
    toast({
      title: 'エクスポート完了',
      description: 'トレースがJSONファイルとしてエクスポートされました',
      status: 'success',
      duration: 3000,
      isClosable: true,
    });
  };
  
  // 時間のフォーマット
  const formatTime = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleString();
  };
  
  // 時間の相対表示
  const getRelativeTime = (timestamp) => {
    const now = new Date();
    const date = new Date(timestamp);
    const diffMs = now - date;
    
    // 秒数に変換
    const diffSec = Math.floor(diffMs / 1000);
    
    if (diffSec < 60) {
      return `${diffSec}秒前`;
    } else if (diffSec < 3600) {
      return `${Math.floor(diffSec / 60)}分前`;
    } else if (diffSec < 86400) {
      return `${Math.floor(diffSec / 3600)}時間前`;
    } else {
      return `${Math.floor(diffSec / 86400)}日前`;
    }
  };
  
  // 期間のフォーマット
  const formatDuration = (duration) => {
    if (duration < 1) {
      return `${(duration * 1000).toFixed(2)}μs`;
    } else if (duration < 1000) {
      return `${duration.toFixed(2)}ms`;
    } else {
      return `${(duration / 1000).toFixed(2)}s`;
    }
  };
  
  // スパンのステータスバッジを取得
  const getStatusBadge = (status) => {
    if (!status) return null;
    
    let color;
    switch (status.toLowerCase()) {
      case 'ok':
      case 'success':
        color = 'green';
        break;
      case 'error':
      case 'failed':
        color = 'red';
        break;
      case 'warning':
        color = 'yellow';
        break;
      case 'unset':
      default:
        color = 'gray';
    }
    
    return (
      <Badge colorScheme={color} fontSize="xs">
        {status}
      </Badge>
    );
  };
  
  // スパンツリーの描画
  const renderSpanTree = (trace) => {
    if (!trace || !trace.spans || trace.spans.length === 0) {
      return (
        <Text fontSize="sm" color={mutedColor}>
          トレースに含まれるスパンがありません
        </Text>
      );
    }
    
    // スパンをIDでインデックス化
    const spanMap = {};
    trace.spans.forEach(span => {
      spanMap[span.span_id] = { ...span, children: [] };
    });
    
    // 親子関係の構築
    const rootSpans = [];
    trace.spans.forEach(span => {
      const mappedSpan = spanMap[span.span_id];
      
      if (span.parent_span_id && spanMap[span.parent_span_id]) {
        spanMap[span.parent_span_id].children.push(mappedSpan);
      } else {
        rootSpans.push(mappedSpan);
      }
    });
    
    // スパンツリーを再帰的に描画する関数
    const renderSpan = (span, depth = 0) => {
      const isExpanded = expandedSpans[span.span_id];
      const hasChildren = span.children && span.children.length > 0;
      const marginLeft = depth * 20;
      
      return (
        <React.Fragment key={span.span_id}>
          <Box 
            p={2} 
            pl={`${marginLeft + 8}px`}
            borderLeft={depth > 0 ? "2px solid" : "none"}
            borderColor={borderColor}
            position="relative"
            _hover={{ bg: hoverBgColor }}
            cursor="pointer"
            onClick={() => toggleSpan(span.span_id)}
          >
            <Flex alignItems="center">
              {hasChildren ? (
                isExpanded ? (
                  <ChevronDownIcon boxSize={4} mr={1} />
                ) : (
                  <ChevronRightIcon boxSize={4} mr={1} />
                )
              ) : (
                <Box w={4} mr={1} />
              )}
              
              <Text fontWeight="medium" fontSize="sm">
                {span.name}
              </Text>
              
              {span.service && (
                <Badge ml={2} colorScheme="blue" fontSize="xs">
                  {span.service}
                </Badge>
              )}
              
              {span.status && getStatusBadge(span.status)}
              
              <Text fontSize="xs" color={mutedColor} ml="auto">
                {formatDuration(span.duration_ms)}
              </Text>
            </Flex>
          </Box>
          
          <Collapse in={isExpanded} animateOpacity>
            <Box pl={`${marginLeft + 20}px`} py={2} bg={useColorModeValue('gray.50', 'gray.700')}>
              <VStack align="stretch" spacing={2}>
                <Box>
                  <Text fontSize="xs" fontWeight="bold" color={mutedColor}>スパンID:</Text>
                  <Code fontSize="xs">{span.span_id}</Code>
                </Box>
                
                {span.parent_span_id && (
                  <Box>
                    <Text fontSize="xs" fontWeight="bold" color={mutedColor}>親スパンID:</Text>
                    <Code fontSize="xs">{span.parent_span_id}</Code>
                  </Box>
                )}
                
                <Box>
                  <Text fontSize="xs" fontWeight="bold" color={mutedColor}>開始時間:</Text>
                  <Text fontSize="xs">{formatTime(span.start_time)}</Text>
                </Box>
                
                {span.attributes && Object.keys(span.attributes).length > 0 && (
                  <Box>
                    <Text fontSize="xs" fontWeight="bold" color={mutedColor}>属性:</Text>
                    <VStack align="stretch" spacing={1} mt={1}>
                      {Object.entries(span.attributes).map(([key, value]) => (
                        <Flex key={key} fontSize="xs">
                          <Text fontWeight="bold" mr={1}>{key}:</Text>
                          <Text>{JSON.stringify(value)}</Text>
                        </Flex>
                      ))}
                    </VStack>
                  </Box>
                )}
                
                {span.events && span.events.length > 0 && (
                  <Box>
                    <Text fontSize="xs" fontWeight="bold" color={mutedColor}>イベント:</Text>
                    <VStack align="stretch" spacing={1} mt={1}>
                      {span.events.map((event, idx) => (
                        <Box key={idx} fontSize="xs" p={1} bg={useColorModeValue('white', 'gray.800')} borderRadius="md">
                          <Flex>
                            <Text fontWeight="bold" mr={1}>{event.name}</Text>
                            <Text ml="auto" color={mutedColor}>{formatTime(event.timestamp)}</Text>
                          </Flex>
                          {event.attributes && Object.keys(event.attributes).length > 0 && (
                            <VStack align="stretch" spacing={0} mt={1}>
                              {Object.entries(event.attributes).map(([key, value]) => (
                                <Flex key={key} fontSize="xs">
                                  <Text fontWeight="bold" mr={1}>{key}:</Text>
                                  <Text>{JSON.stringify(value)}</Text>
                                </Flex>
                              ))}
                            </VStack>
                          )}
                        </Box>
                      ))}
                    </VStack>
                  </Box>
                )}
              </VStack>
            </Box>
          </Collapse>
          
          {isExpanded && span.children && span.children.map(child => renderSpan(child, depth + 1))}
        </React.Fragment>
      );
    };
    
    return (
      <VStack align="stretch" spacing={0} mt={4} border="1px solid" borderColor={borderColor} borderRadius="md" overflow="hidden">
        {rootSpans.map(span => renderSpan(span))}
      </VStack>
    );
  };
  
  return (
    <Box p={5}>
      <Heading size="lg" mb={6}>トレースビューアー</Heading>
      
      {/* フィルターと検索 */}
      <Flex flexWrap="wrap" gap={4} mb={4}>
        <Box flex="1" minW="200px">
          <Input
            placeholder="トレースID、名前、属性で検索..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            leftElement={<SearchIcon color="gray.300" />}
          />
        </Box>
        
        <Select 
          value={timeRange} 
          onChange={(e) => setTimeRange(e.target.value)} 
          w="auto"
          minW="150px"
        >
          <option value="15m">15分</option>
          <option value="30m">30分</option>
          <option value="1h">1時間</option>
          <option value="3h">3時間</option>
          <option value="6h">6時間</option>
          <option value="12h">12時間</option>
          <option value="24h">1日</option>
          <option value="7d">1週間</option>
        </Select>
        
        <Select 
          value={serviceFilter} 
          onChange={(e) => setServiceFilter(e.target.value)} 
          w="auto"
          minW="200px"
          placeholder="すべてのサービス"
        >
          {services.map(service => (
            <option key={service} value={service}>{service}</option>
          ))}
        </Select>
        
        <Select 
          value={statusFilter} 
          onChange={(e) => setStatusFilter(e.target.value)} 
          w="auto"
          minW="150px"
        >
          <option value="all">すべてのステータス</option>
          <option value="ok">成功</option>
          <option value="error">エラー</option>
        </Select>
        
        <Tooltip label="更新">
          <IconButton 
            icon={<RepeatIcon />} 
            aria-label="更新" 
            onClick={fetchTraces}
            isLoading={loading}
          />
        </Tooltip>
      </Flex>
      
      {/* エラー表示 */}
      {error && (
        <Alert status="error" mb={4}>
          <AlertIcon />
          {error}
        </Alert>
      )}
      
      <Flex direction={{ base: 'column', lg: 'row' }} gap={6}>
        {/* トレース一覧 */}
        <Box 
          flex="1" 
          overflowX="auto" 
          borderRadius="md" 
          boxShadow="sm" 
          bg={bgColor} 
          borderWidth="1px"
          borderColor={borderColor}
        >
          <Table variant="simple" size="sm" ref={tableRef}>
            <Thead>
              <Tr>
                <Th 
                  cursor="pointer" 
                  onClick={() => toggleSort('name')}
                  color={sortBy === 'name' ? 'blue.500' : undefined}
                >
                  名前
                  {sortBy === 'name' && (
                    sortDirection === 'asc' ? '↑' : '↓'
                  )}
                </Th>
                <Th 
                  cursor="pointer" 
                  onClick={() => toggleSort('timestamp')}
                  color={sortBy === 'timestamp' ? 'blue.500' : undefined}
                >
                  時間
                  {sortBy === 'timestamp' && (
                    sortDirection === 'asc' ? '↑' : '↓'
                  )}
                </Th>
                <Th 
                  cursor="pointer" 
                  onClick={() => toggleSort('duration')}
                  color={sortBy === 'duration' ? 'blue.500' : undefined}
                  isNumeric
                >
                  期間
                  {sortBy === 'duration' && (
                    sortDirection === 'asc' ? '↑' : '↓'
                  )}
                </Th>
                <Th 
                  cursor="pointer" 
                  onClick={() => toggleSort('spanCount')}
                  color={sortBy === 'spanCount' ? 'blue.500' : undefined}
                  isNumeric
                >
                  スパン数
                  {sortBy === 'spanCount' && (
                    sortDirection === 'asc' ? '↑' : '↓'
                  )}
                </Th>
              </Tr>
            </Thead>
            <Tbody>
              {loading && !filteredTraces.length ? (
                <Tr>
                  <Td colSpan={4} textAlign="center" py={10}>
                    <Spinner size="lg" />
                    <Text mt={2}>トレースを読み込み中...</Text>
                  </Td>
                </Tr>
              ) : filteredTraces.length === 0 ? (
                <Tr>
                  <Td colSpan={4} textAlign="center" py={10}>
                    <Text>該当するトレースが見つかりません</Text>
                  </Td>
                </Tr>
              ) : (
                filteredTraces.map((trace) => (
                  <Tr 
                    key={trace.trace_id}
                    cursor="pointer"
                    onClick={() => handleSelectTrace(trace)}
                    bg={selectedTrace?.trace_id === trace.trace_id ? selectedBgColor : undefined}
                    _hover={{ bg: selectedTrace?.trace_id === trace.trace_id ? selectedBgColor : hoverBgColor }}
                  >
                    <Td>
                      <Text fontWeight="medium">{trace.name}</Text>
                      <Text fontSize="xs" color={mutedColor}>{trace.trace_id.substring(0, 8)}...</Text>
                    </Td>
                    <Td>
                      <Tooltip label={formatTime(trace.start_time)}>
                        <Text>{getRelativeTime(trace.start_time)}</Text>
                      </Tooltip>
                    </Td>
                    <Td isNumeric>{formatDuration(trace.duration_ms)}</Td>
                    <Td isNumeric>{trace.spans.length}</Td>
                  </Tr>
                ))
              )}
            </Tbody>
          </Table>
        </Box>
        
        {/* トレース詳細 */}
        <Box 
          flex="1" 
          borderRadius="md" 
          boxShadow="sm" 
          bg={bgColor} 
          borderWidth="1px"
          borderColor={borderColor}
          p={4}
          minH="60vh"
          overflowY="auto"
        >
          {selectedTrace ? (
            <>
              <Flex justifyContent="space-between" alignItems="center">
                <Heading size="md" mb={4}>{selectedTrace.name}</Heading>
                <Tooltip label="JSONとしてエクスポート">
                  <IconButton 
                    size="sm"
                    icon={<DownloadIcon />} 
                    aria-label="エクスポート" 
                    onClick={exportTraceJson}
                  />
                </Tooltip>
              </Flex>
              
              <Flex flexWrap="wrap" gap={4} fontSize="sm" mb={4}>
                <Box>
                  <Text fontWeight="bold" color={mutedColor}>トレースID:</Text>
                  <Code>{selectedTrace.trace_id}</Code>
                </Box>
                <Box>
                  <Text fontWeight="bold" color={mutedColor}>時間:</Text>
                  <Text>{formatTime(selectedTrace.start_time)}</Text>
                </Box>
                <Box>
                  <Text fontWeight="bold" color={mutedColor}>期間:</Text>
                  <Text>{formatDuration(selectedTrace.duration_ms)}</Text>
                </Box>
                <Box>
                  <Text fontWeight="bold" color={mutedColor}>スパン数:</Text>
                  <Text>{selectedTrace.spans.length}</Text>
                </Box>
              </Flex>
              
              <Divider my={4} />
              
              {renderSpanTree(selectedTrace)}
            </>
          ) : (
            <Flex 
              direction="column" 
              justify="center" 
              align="center" 
              h="100%" 
              color={mutedColor}
            >
              <InfoIcon boxSize={10} mb={4} />
              <Text>トレースを選択してください</Text>
            </Flex>
          )}
        </Box>
      </Flex>
    </Box>
  );
};

export default TraceViewer; 